"""Audio endpoint tests; provider calls are always mocked."""
from uuid import UUID, uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.interview import InterviewAnswer
from app.schemas.interview import GeneratedQuestion, DifficultyEnum
from app.services.resumes.gemini_service import heuristic_answer_evaluation
from tests.test_interviews import create_application
from tests.test_applications import premium_token_for
from tests.test_auth import client

AUDIO = b"\x1a\x45\xdf\xa3" + b"mock audio payload"
TRANSCRIPT = "I use Python and automated tests to validate API behavior."


@pytest.fixture
def session(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_local_dir", str(tmp_path))
    monkeypatch.setattr(settings, "storage_backend", "local")
    async def transcribe(*args):
        return TRANSCRIPT
    monkeypatch.setattr("app.api.routes.interviews.transcribe_audio", transcribe)
    contexts = []
    async def generate(**kwargs):
        contexts.append(kwargs)
        return GeneratedQuestion(question="How do you test a Python API?", topic="Python", question_type="technical",
                                 difficulty=DifficultyEnum.medium, expected_skills=["Python"], reason="Tests API skills")
    monkeypatch.setattr("app.api.routes.interviews.generate_question_for_application", generate)
    headers = premium_token_for(f"audio-{uuid4()}@example.com", "Audio Owner")
    application = create_application(headers)
    iid = client.post("/api/v1/interviews", headers=headers, json={"application_id": application,
                      "personality": "technical", "difficulty": "medium"}).json()["data"]["interview_id"]
    base = f"/api/v1/interviews/{iid}"
    qid = client.post(base + "/questions", headers=headers).json()["data"]["question_id"]
    return SimpleNamespace(headers=headers, base=base, qid=qid, url=f"{base}/questions/{qid}/audio-answer", contexts=contexts, root=tmp_path)


def upload(s, data=AUDIO, mime="audio/webm", headers=None):
    return client.post(s.url, headers=s.headers if headers is None else headers,
                       files={"audio": ("../../untrusted.webm", data, mime)}, data={"duration_seconds": "4.5"})


def test_audio_saved_evaluated_adaptive_and_replaced(session, monkeypatch):
    s = session
    seen = []
    class Evaluator:
        def evaluate_interview_answer(self, **kwargs):
            seen.append(kwargs["answer_text"])
            return heuristic_answer_evaluation(**kwargs)
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: Evaluator())
    response = upload(s)
    assert response.status_code == 200, response.text
    answer = response.json()["data"]
    assert answer["answer_text"] == TRANSCRIPT
    assert answer["source"] == "voice"
    assert "audio_storage_key" not in answer
    aid = answer["answer_id"]
    assert client.post(f"{s.base}/answers/{aid}/evaluate", headers=s.headers).status_code == 200
    assert seen == [TRANSCRIPT]
    for _ in range(2):
        assert client.post(s.base + "/questions", headers=s.headers).status_code == 200
    assert s.contexts[-1]["adaptation"] is not None
    assert upload(s).json()["data"]["answer_id"] == aid
    with SessionLocal() as db:
        rows = db.scalars(select(InterviewAnswer).where(InterviewAnswer.question_id == UUID(s.qid))).all()
        assert len(rows) == 1
        assert rows[0].answer_text == TRANSCRIPT
        assert rows[0].audio_size_bytes == len(AUDIO)
        assert rows[0].evaluation is None
        assert (s.root / rows[0].audio_storage_key).read_bytes() == AUDIO
    assert len(list(s.root.rglob("*.webm"))) == 1
    typed = client.post(s.base + "/answers", headers=s.headers, json={"question_id": s.qid, "answer_text": "Typed replacement"})
    assert typed.status_code == 200
    assert typed.json()["data"]["answer_id"] == aid
    assert typed.json()["data"]["source"] == "typed"
    assert not list(s.root.rglob("*.webm"))


def test_audio_auth_and_ownership(session):
    assert upload(session, headers={}).status_code == 401
    other = premium_token_for(f"other-{uuid4()}@example.com", "Other")
    assert upload(session, headers=other).status_code == 404
    response = client.post(f"{session.base}/questions/{uuid4()}/audio-answer", headers=session.headers,
                           files={"audio": ("a.webm", AUDIO, "audio/webm")})
    assert response.status_code == 404


@pytest.mark.parametrize("data,mime,code", [(b"", "audio/webm", 422), (AUDIO, "text/plain", 415), (b"fake", "audio/webm", 415), (b"x" * (1024 * 1024 + 1), "audio/webm", 413)], ids=["empty", "unsupported", "spoofed", "oversized"])
def test_audio_validation(session, monkeypatch, data, mime, code):
    monkeypatch.setattr(get_settings(), "interview_audio_max_mb", 1)
    assert upload(session, data, mime).status_code == code
    assert not list(session.root.rglob("*.webm"))


def test_transcription_failure_preserves_answer(session, monkeypatch):
    first = upload(session).json()["data"]
    async def fail(*args):
        raise HTTPException(502, "Transcription failed")
    monkeypatch.setattr("app.api.routes.interviews.transcribe_audio", fail)
    assert upload(session).status_code == 502
    full = client.get(session.base + "/full", headers=session.headers).json()["data"]
    assert full["items"][0]["answer"]["answer_id"] == first["answer_id"]
    assert len(list(session.root.rglob("*.webm"))) == 1


@pytest.mark.parametrize("result,code", [("  spoken answer  ", None), ("", 422), ("x" * 12001, 422)], ids=["transcript", "silence", "long"])
def test_gemini_transcription_adapter(monkeypatch, result, code):
    import asyncio
    from google import genai
    from app.services.interview_audio import transcribe_audio
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_transcription_model", "test-audio-model")
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=result)
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    if code:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(transcribe_audio(AUDIO, "audio/webm"))
        assert exc.value.status_code == code
    else:
        assert asyncio.run(transcribe_audio(AUDIO, "audio/webm")) == "spoken answer"
    assert calls[0]["model"] == "test-audio-model"
    assert calls[0]["contents"][0].inline_data.data == AUDIO


def test_gemini_missing_configuration(monkeypatch):
    import asyncio
    from app.services.interview_audio import transcribe_audio
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(transcribe_audio(AUDIO, "audio/webm"))
    assert exc.value.status_code == 503
