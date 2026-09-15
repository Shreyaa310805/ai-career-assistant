"""Video interview mode: creation, frame sampling lifecycle, final answers and visual scoring."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.interview import DifficultyEnum, GeneratedFrameAnalysis, GeneratedQuestion
from app.services.interview_visual import aggregate_visual_analysis
from app.services.resumes.gemini_service import heuristic_answer_evaluation, heuristic_interview_summary
from tests.test_applications import premium_token_for
from tests.test_auth import client
from tests.test_interviews import create_application

JPEG = b"\xff\xd8\xff\xe0" + b"mock jpeg payload"
AUDIO = b"\x1a\x45\xdf\xa3" + b"mock audio payload"


def frame_result(**overrides):
    values = dict(face_visible=True, multiple_people=False, looking_at_camera=True, engagement_score=80,
                  attentiveness_score=70, composure_score=90, presentation_score=60, expression="Neutral",
                  observation="Face centered with even lighting.")
    values.update(overrides)
    return GeneratedFrameAnalysis(**values)


@pytest.fixture
def video(monkeypatch, tmp_path):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "storage_local_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "storage_backend", "local")
    results = []
    async def analyze(data):
        assert data == JPEG
        return results.pop(0) if results else frame_result()
    async def transcribe(*args):
        return "I would profile the endpoint and add caching."
    async def generate(**kwargs):
        return GeneratedQuestion(question="How would you speed up a slow API?", topic="Performance",
                                 question_type="technical", difficulty=DifficultyEnum.medium,
                                 expected_skills=["Python"], reason="Checks performance skills")
    monkeypatch.setattr("app.api.routes.interviews.analyze_frame", analyze)
    monkeypatch.setattr("app.api.routes.interviews.transcribe_audio", transcribe)
    monkeypatch.setattr("app.api.routes.interviews.generate_question_for_application", generate)
    class HeuristicGemini:
        def evaluate_interview_answer(self, **kwargs):
            return heuristic_answer_evaluation(**kwargs)

        def generate_interview_summary(self, **kwargs):
            return heuristic_interview_summary(**kwargs)

    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: HeuristicGemini())
    headers = premium_token_for(f"video-{uuid4()}@example.com", "Video Owner")
    application = create_application(headers)
    created = client.post("/api/v1/interviews", headers=headers, json={
        "application_id": application, "personality": "technical", "difficulty": "medium", "mode": "video",
    })
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    return SimpleNamespace(headers=headers, base=f"/api/v1/interviews/{data['interview_id']}", data=data, results=results)


def send_frame(v, data=JPEG, mime="image/jpeg", question_id=None):
    form = {"question_id": question_id} if question_id else {}
    return client.post(v.base + "/visual-frames", headers=v.headers, files={"frame": ("f.jpg", data, mime)}, data=form)


def test_mode_defaults_to_text_and_video_is_persisted(video):
    assert video.data["mode"] == "video"
    full = client.get(video.base + "/full", headers=video.headers).json()["data"]
    assert full["mode"] == "video"
    assert full["visual_analysis"] is None
    application = create_application(video.headers)
    text = client.post("/api/v1/interviews", headers=video.headers, json={
        "application_id": application, "personality": "technical", "difficulty": "medium"})
    assert text.json()["data"]["mode"] == "text"
    bad = client.post("/api/v1/interviews", headers=video.headers, json={
        "application_id": application, "personality": "technical", "difficulty": "medium", "mode": "hologram"})
    assert bad.status_code == 422


def test_frames_rejected_before_start_and_after_completion(video):
    assert send_frame(video).status_code == 409
    question = client.post(video.base + "/questions", headers=video.headers).json()["data"]
    ok = send_frame(video, question_id=question["question_id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["frames_analyzed"] == 1
    assert client.post(video.base + "/complete", headers=video.headers).status_code == 200
    assert send_frame(video).status_code == 409


def test_frames_rejected_for_text_interviews(video):
    application = create_application(video.headers)
    iid = client.post("/api/v1/interviews", headers=video.headers, json={
        "application_id": application, "personality": "technical", "difficulty": "medium", "mode": "audio",
    }).json()["data"]["interview_id"]
    base = f"/api/v1/interviews/{iid}"
    client.post(base + "/questions", headers=video.headers)
    response = client.post(base + "/visual-frames", headers=video.headers, files={"frame": ("f.jpg", JPEG, "image/jpeg")})
    assert response.status_code == 409


@pytest.mark.parametrize("data,mime,code", [(JPEG, "image/png", 415), (b"not a jpeg", "image/jpeg", 415),
                                             (b"\xff\xd8\xff" + b"x" * (1024 * 1024), "image/jpeg", 413)],
                         ids=["mime", "spoofed", "oversized"])
def test_frame_validation(video, data, mime, code):
    client.post(video.base + "/questions", headers=video.headers)
    assert send_frame(video, data, mime).status_code == code


def test_frame_ownership(video):
    client.post(video.base + "/questions", headers=video.headers)
    other = premium_token_for(f"video-other-{uuid4()}@example.com", "Other")
    response = client.post(video.base + "/visual-frames", headers=other, files={"frame": ("f.jpg", JPEG, "image/jpeg")})
    assert response.status_code == 404


def test_video_answers_are_final(video):
    question = client.post(video.base + "/questions", headers=video.headers).json()["data"]
    url = f"{video.base}/questions/{question['question_id']}/audio-answer"
    first = client.post(url, headers=video.headers, files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert first.status_code == 200, first.text
    again = client.post(url, headers=video.headers, files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert again.status_code == 409
    typed = client.post(video.base + "/answers", headers=video.headers,
                        json={"question_id": question["question_id"], "answer_text": "replacement"})
    assert typed.status_code == 409


def test_visual_score_generated_from_analyzed_frames(video):
    question = client.post(video.base + "/questions", headers=video.headers).json()["data"]
    video.results.extend([
        frame_result(),
        frame_result(looking_at_camera=False, engagement_score=60, attentiveness_score=50,
                     composure_score=70, presentation_score=40, expression="looking down"),
        frame_result(face_visible=False, looking_at_camera=False, engagement_score=0, attentiveness_score=0,
                     composure_score=0, presentation_score=0, expression="not visible", observation=""),
    ])
    for _ in range(3):
        assert send_frame(video, question_id=question["question_id"]).status_code == 200
    completed = client.post(video.base + "/complete", headers=video.headers).json()["data"]
    visual = completed["visual_analysis"]
    assert visual["frames_analyzed"] == 3
    assert visual["face_visible_rate"] == pytest.approx(0.667, abs=0.001)
    assert visual["eye_contact_rate"] == 0.5
    assert visual["engagement"] == pytest.approx(46.7, abs=0.1)
    # 0.25*46.67 + 0.2*40 + 0.2*53.33 + 0.15*33.33 + 0.1*50 + 0.1*66.67
    assert visual["visual_score"] == 47
    assert "neutral" in visual["common_expressions"]
    full = client.get(video.base + "/full", headers=video.headers).json()["data"]
    assert full["visual_analysis"] == visual
    history = client.get("/api/v1/interviews", headers=video.headers).json()["data"]["items"]
    assert next(i for i in history if i["interview_id"] == video.data["interview_id"])["visual_score"] == 47


def test_video_completion_without_frames_has_no_visual_score(video):
    client.post(video.base + "/questions", headers=video.headers)
    completed = client.post(video.base + "/complete", headers=video.headers).json()["data"]
    assert completed["visual_analysis"] is None


def test_aggregate_empty_and_multiple_people():
    assert aggregate_visual_analysis([]) is None
    frame = SimpleNamespace(**frame_result(multiple_people=True).model_dump())
    result = aggregate_visual_analysis([frame])
    assert result.visual_score == round(0.25 * 80 + 0.2 * 70 + 0.2 * 90 + 0.15 * 60 + 10 + 10)
    assert result.observations[0].startswith("More than one person")


def test_analyze_frame_requires_configuration(monkeypatch):
    import asyncio
    from app.core.config import get_settings
    from app.services.interview_visual import analyze_frame
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(analyze_frame(JPEG))
    assert exc.value.status_code == 503


def test_analyze_frame_gemini_adapter(monkeypatch):
    import asyncio
    from google import genai
    from app.core.config import get_settings
    from app.services.interview_visual import analyze_frame
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "gemini_vision_model", "test-vision-model")
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=frame_result().model_dump_json())
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    assert asyncio.run(analyze_frame(JPEG)).engagement_score == 80
    assert calls[0]["model"] == "test-vision-model"
    assert calls[0]["contents"][0].inline_data.data == JPEG
