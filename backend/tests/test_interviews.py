import asyncio
from types import SimpleNamespace

from tests.test_applications import premium_token_for, token_for
from tests.test_auth import client
from app.schemas.interview import DifficultyEnum, GeneratedQuestion
from app.services.interview_questions import generate_question_for_application
from app.services.resumes.gemini_service import GeminiService, heuristic_interview_question


def create_application(headers: dict[str, str]) -> str:
    response = client.post("/api/v1/applications", headers=headers, json={"company": "Acme", "role": "Engineer"})
    assert response.status_code == 201
    return response.json()["id"]


def test_interview_creation_preserves_contract_and_requires_premium():
    free = token_for("interview-free@example.com", "Interview Free")
    response = client.post(
        "/api/v1/interviews",
        headers=free,
        json={"application_id": "00000000-0000-0000-0000-000000000001", "personality": "technical", "difficulty": "medium"},
    )
    assert response.status_code == 403

    owner = premium_token_for("interview-owner@example.com", "Interview Owner")
    application_id = create_application(owner)
    created = client.post(
        "/api/v1/interviews",
        headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    )
    assert created.status_code == 200
    assert created.json()["success"] is True
    assert created.json()["error"] is None
    assert created.json()["data"] == {
        "interview_id": created.json()["data"]["interview_id"],
        "application_id": application_id,
        "personality": "technical",
        "difficulty": "medium",
        "status": "created",
        "question_count": 0,
        "started_at": None,
    }


def test_interviews_are_owner_scoped():
    owner = premium_token_for("interview-scope-owner@example.com", "Interview Owner")
    other = premium_token_for("interview-scope-other@example.com", "Interview Other")
    application_id = create_application(owner)
    created = client.post(
        "/api/v1/interviews",
        headers=owner,
        json={"application_id": application_id, "personality": "mixed", "difficulty": "hard"},
    )
    interview_id = created.json()["data"]["interview_id"]
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=other).status_code == 404
    assert client.post(
        "/api/v1/interviews",
        headers=other,
        json={"application_id": application_id, "personality": "mixed", "difficulty": "hard"},
    ).status_code == 404


def test_question_generation_persists_orders_and_is_owner_scoped(monkeypatch):
    owner = premium_token_for("question-owner@example.com", "Question Owner")
    other = premium_token_for("question-other@example.com", "Question Other")
    application_id = create_application(owner)
    interview = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]

    generation_contexts = []

    class FakeGemini:
        def generate_interview_question(self, **context):
            generation_contexts.append(context)
            return GeneratedQuestion(
                question=f"How would you use Python for question {context['question_number']}?",
                topic="Python", question_type="technical", difficulty=DifficultyEnum.medium,
                expected_skills=["Python"], reason="Tests a skill from the application context.",
            )

    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    first = client.post(f"/api/v1/interviews/{interview['interview_id']}/questions", headers=owner, json={"mode": "standard"})
    assert first.status_code == 200
    assert first.json()["data"]["question_number"] == 1
    second = client.post(f"/api/v1/interviews/{interview['interview_id']}/questions", headers=owner, json={"mode": "adaptive"})
    assert second.status_code == 200
    assert second.json()["data"]["question_number"] == 2
    assert generation_contexts[0]["previous_questions"] == []
    assert generation_contexts[1]["previous_questions"] == [first.json()["data"]["question"]]

    listed = client.get(f"/api/v1/interviews/{interview['interview_id']}/questions", headers=owner)
    assert listed.status_code == 200
    assert [item["question_number"] for item in listed.json()["data"]["questions"]] == [1, 2]
    session = client.get(f"/api/v1/interviews/{interview['interview_id']}", headers=owner)
    assert session.json()["data"]["question_count"] == 2
    assert client.get(f"/api/v1/interviews/{interview['interview_id']}/questions", headers=other).status_code == 404
    assert client.post("/api/v1/interviews/00000000-0000-0000-0000-000000000001/questions", headers=owner, json={"mode": "standard"}).status_code == 404

    second_session = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "friendly", "difficulty": "easy"},
    ).json()["data"]
    assert client.post(f"/api/v1/interviews/{second_session['interview_id']}/questions", headers=owner, json={"mode": "standard"}).status_code == 200
    assert generation_contexts[2]["previous_questions"] == [
        first.json()["data"]["question"], second.json()["data"]["question"],
    ]

    other_application_id = create_application(owner)
    other_session = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": other_application_id, "personality": "friendly", "difficulty": "easy"},
    ).json()["data"]
    assert client.post(f"/api/v1/interviews/{other_session['interview_id']}/questions", headers=owner, json={"mode": "standard"}).status_code == 200
    assert generation_contexts[3]["previous_questions"] == []


def test_question_generation_fallback_result_is_persisted(monkeypatch):
    owner = premium_token_for("question-fallback@example.com", "Question Fallback")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "mixed", "difficulty": "easy"},
    ).json()["data"]["interview_id"]

    class FallbackGemini:
        def generate_interview_question(self, **context):
            return GeneratedQuestion(
                question="How would you apply Engineer role fundamentals to a realistic role problem?",
                topic="Engineer", question_type="mixed", difficulty=DifficultyEnum.easy,
                expected_skills=["Engineer"], reason="Fallback after invalid AI output.",
            )

    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FallbackGemini())
    response = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner, json={"mode": "standard"})
    assert response.status_code == 200
    assert response.json()["data"]["question_number"] == 1


def test_question_fallback_changes_wording_for_one_skill_and_replaces_duplicate_gemini_result(monkeypatch):
    first = heuristic_interview_question(
        role="Backend Intern", personality="behavioral", difficulty=DifficultyEnum.medium,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence="",
    )
    second = heuristic_interview_question(
        role="Backend Intern", personality="behavioral", difficulty=DifficultyEnum.medium,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=2,
        previous_questions=[first.question], resume_evidence="",
    )
    assert first.question != second.question

    service = GeminiService()
    service._client = object()
    monkeypatch.setattr(service, "_generate_interview_question_via_gemini", lambda **_: first)
    generated = service.generate_interview_question(
        role="Backend Intern", job_description="Python backend internship", personality="behavioral",
        difficulty=DifficultyEnum.medium, resume_skills=["Python"], matched_skills=[], missing_skills=[],
        question_number=2, previous_questions=[first.question], resume_evidence="",
    )
    assert generated.question != first.question


def test_resume_project_context_is_in_prompt_and_fallback_question(monkeypatch):
    resume_evidence = """Projects
Ride & Food Delivery Simulation — Python, Flask, PostgreSQL, REST APIs
Built delivery tracking and order management flows.
"""
    prompt = GeminiService._interview_question_prompt(
        role="Backend Intern", job_description="Build REST APIs with PostgreSQL", personality="technical",
        difficulty=DifficultyEnum.medium, resume_skills=["Python", "Flask"], matched_skills=["REST APIs"],
        missing_skills=["PostgreSQL"], question_number=1, previous_questions=[], resume_evidence=resume_evidence,
    )
    assert "Ride & Food Delivery Simulation" in prompt
    question = heuristic_interview_question(
        role="Backend Intern", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["Python", "Flask"], matched_skills=["REST APIs"], missing_skills=["PostgreSQL"],
        question_number=1, previous_questions=[], resume_evidence=resume_evidence,
    )
    assert "Ride & Food Delivery Simulation" in question.question
    assert "consideration" not in question.question.lower()


def test_resume_project_evidence_reaches_question_generator(monkeypatch):
    resume = SimpleNamespace(
        parsed_data={"skills": ["Python", "Flask"]},
        raw_text="Projects\nRide & Food Delivery Simulation — Python, Flask, PostgreSQL, REST APIs",
        id="resume-id",
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalars(self):
            return self

        def first(self):
            return self.value

    class ResumeDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, _statement):
            self.calls += 1
            return Result(resume if self.calls == 1 else None)

    captured = {}

    class FakeGemini:
        def generate_interview_question(self, **context):
            captured.update(context)
            return GeneratedQuestion(
                question="How did you design the delivery API?", topic="REST APIs", question_type="project_deep_dive",
                difficulty=DifficultyEnum.medium, expected_skills=["Flask"], reason="Uses project context.",
            )

    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    application = SimpleNamespace(id="application-id", role="Backend Intern", job_description="Build REST APIs")
    asyncio.run(generate_question_for_application(
        application=application, personality="technical", difficulty="medium", question_number=1,
        previous_questions=[], resume_db=ResumeDb(),
    ))
    assert "Ride & Food Delivery Simulation" in captured["resume_evidence"]


def test_fallback_enforces_behavioral_intent_and_does_not_force_soft_skills():
    evidence = "Projects\nInventory Management API — Python, Flask, REST APIs"
    behavioral = heuristic_interview_question(
        role="Associate SWE", personality="behavioral", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    assert behavioral.question_type == "behavioral"
    assert "challenge" in behavioral.question.lower()
    assert "how would you scale" not in behavioral.question.lower()

    technical = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    assert technical.question_type == "project_deep_dive"
    assert "Inventory Management API" in technical.question

    soft_skill = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.easy,
        resume_skills=["communication skills"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence="",
    )
    assert "communication skills" not in soft_skill.question.lower()
    assert "consideration" not in soft_skill.question.lower()


def test_fallback_uses_distinct_angles_without_fake_uniqueness():
    evidence = "Projects\nInventory Management API — Python, MySQL, REST APIs"
    technical_one = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    technical_two = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=2,
        previous_questions=[technical_one.question], resume_evidence=evidence,
    )
    assert technical_one.question != technical_two.question
    assert "bug" in technical_two.question.lower() or "edge case" in technical_two.question.lower()

    behavioral_one = heuristic_interview_question(
        role="Associate SWE", personality="behavioral", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    behavioral_two = heuristic_interview_question(
        role="Associate SWE", personality="behavioral", difficulty=DifficultyEnum.medium,
        resume_skills=["REST APIs"], matched_skills=[], missing_skills=[], question_number=2,
        previous_questions=[behavioral_one.question], resume_evidence=evidence,
    )
    assert behavioral_one.question_type == behavioral_two.question_type == "behavioral"
    assert behavioral_one.question != behavioral_two.question
    assert "Describe a different approach than the earlier response" not in behavioral_two.question

    friendly_one = heuristic_interview_question(
        role="Associate SWE", personality="friendly", difficulty=DifficultyEnum.easy,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    friendly_two = heuristic_interview_question(
        role="Associate SWE", personality="friendly", difficulty=DifficultyEnum.easy,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=2,
        previous_questions=[friendly_one.question], resume_evidence=evidence,
    )
    assert friendly_one.question != friendly_two.question


def test_role_is_not_used_as_a_fallback_topic():
    question = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.easy,
        resume_skills=[], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence="",
    )
    assert "implement Associate SWE" not in question.question
    assert question.expected_skills == []


def test_fallback_broadens_project_context_without_changing_angles():
    evidence = """Projects
SplitWise Matrix App - Python, SQL
Inventory Management API - Python, MySQL, REST APIs
Smart House Price Predictor - Python, Random Forest
Experience
Software Engineering Intern
"""
    first = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence=evidence,
    )
    second = heuristic_interview_question(
        role="Associate SWE", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=["Python"], matched_skills=[], missing_skills=[], question_number=2,
        previous_questions=[first.question], resume_evidence=evidence,
    )
    assert "SplitWise Matrix App" in first.question
    assert "SplitWise Matrix App" not in second.question
    assert any(name in second.question for name in ("Inventory Management API", "Smart House Price Predictor"))
    assert first.question != second.question
