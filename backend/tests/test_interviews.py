import asyncio
from types import SimpleNamespace

from tests.test_applications import premium_token_for, token_for
from tests.test_auth import client
from app.schemas.interview import DifficultyEnum, GeneratedQuestion
from app.services.interview_questions import generate_question_for_application
from app.schemas.interview import GeneratedAnswerEvaluation, GeneratedInterviewSummary, RecommendationEnum
from app.services.resumes.gemini_service import (
    GeminiService,
    heuristic_answer_evaluation,
    heuristic_confidence,
    heuristic_interview_question,
)


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
        "question_target": 5,
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


def test_question_fallback_has_a_valid_topic_when_no_skills_are_available(monkeypatch):
    fallback = heuristic_interview_question(
        role="Backend Intern", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=[], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence="Projects\nRide and Food Sharing Application - Python, PostgreSQL\n",
    )
    assert fallback.topic == "Ride and Food Sharing Application"
    assert fallback.question
    assert fallback.expected_skills == []

    service = GeminiService()
    service._client = object()
    monkeypatch.setattr(
        service, "_generate_interview_question_via_gemini",
        lambda **_: (_ for _ in ()).throw(RuntimeError("503 UNAVAILABLE")),
    )
    generated = service.generate_interview_question(
        role="Backend Intern", job_description="", personality="technical", difficulty=DifficultyEnum.medium,
        resume_skills=[], matched_skills=[], missing_skills=[], question_number=1,
        previous_questions=[], resume_evidence="",
    )
    assert generated.topic == "Backend Intern"
    assert generated.question
    assert generated.expected_skills == []


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


def create_interview_question(headers: dict[str, str], monkeypatch, *, personality="technical") -> tuple[str, str]:
    application_id = create_application(headers)
    interview_id = client.post(
        "/api/v1/interviews", headers=headers,
        json={"application_id": application_id, "personality": personality, "difficulty": "medium"},
    ).json()["data"]["interview_id"]

    class FakeGemini:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a Python service that handles invalid requests?",
                topic="Python", question_type="behavioral" if personality == "behavioral" else "technical", difficulty=DifficultyEnum.medium,
                expected_skills=["Python"], reason="Tests answer submission and evaluation.",
            )

    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    question = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=headers, json={}).json()["data"]
    return interview_id, question["question_id"]


def submit_answer(headers: dict[str, str], interview_id: str, question_id: str, **overrides):
    payload = {
        "question_id": question_id,
        "answer_text": "I would validate input at the API boundary, return useful errors, and add tests for invalid cases.",
        "source": "typed",
        **overrides,
    }
    return client.post(f"/api/v1/interviews/{interview_id}/answers", headers=headers, json=payload)


def test_answer_submission_validates_question_source_duration_and_blank_input(monkeypatch):
    owner = premium_token_for("answer-owner@example.com", "Answer Owner")
    interview_id, question_id = create_interview_question(owner, monkeypatch)

    typed = submit_answer(owner, interview_id, question_id)
    assert typed.status_code == 200
    assert typed.json()["data"]["source"] == "typed"
    assert typed.json()["data"]["duration_seconds"] is None

    voice = submit_answer(owner, interview_id, question_id, source="voice", duration_seconds=42)
    assert voice.status_code == 200
    assert voice.json()["data"]["source"] == "voice"
    assert voice.json()["data"]["duration_seconds"] == 42

    assert submit_answer(owner, interview_id, question_id, answer_text="   ").status_code == 422
    assert submit_answer(owner, interview_id, "00000000-0000-0000-0000-000000000001").status_code == 404


def test_answer_submission_requires_owner_and_same_interview_question(monkeypatch):
    owner = premium_token_for("answer-scope-owner@example.com", "Answer Scope Owner")
    other = premium_token_for("answer-scope-other@example.com", "Answer Scope Other")
    first_interview, first_question = create_interview_question(owner, monkeypatch)
    second_interview, second_question = create_interview_question(owner, monkeypatch)

    assert submit_answer(owner, first_interview, second_question).status_code == 404
    assert submit_answer(other, first_interview, first_question).status_code == 404


def fake_evaluator(*, overall=78):
    class FakeGemini:
        def evaluate_interview_answer(self, **context):
            return GeneratedAnswerEvaluation(
                overall_score=overall, relevance_score=80, correctness_score=75, depth_score=70,
                clarity_score=85, evidence_score=65, confidence_score=72,
                confidence_rationale="Decisive phrasing with no hedging detected.",
                strengths=["Directly answers the question."],
                weaknesses=["Could include an edge case."], missing_points=["A concrete example"],
                feedback=f"Evaluated {context['question_type']} answer.",
            )
    return FakeGemini()


def test_answer_evaluation_is_structured_and_idempotently_updates(monkeypatch):
    owner = premium_token_for("evaluation-owner@example.com", "Evaluation Owner")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator())

    first = client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    second = client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    assert first.status_code == second.status_code == 200
    data = first.json()["data"]
    assert data["evaluation_id"] == second.json()["data"]["evaluation_id"]
    assert data["overall_score"] == 78
    assert {"relevance_score", "correctness_score", "depth_score", "clarity_score", "evidence_score", "strengths", "weaknesses", "missing_points", "feedback"} <= data.keys()


def test_behavioral_answer_uses_behavioral_context_and_weak_fallback_scores_low(monkeypatch):
    owner = premium_token_for("behavioral-evaluation@example.com", "Behavioral Evaluation")
    interview_id, question_id = create_interview_question(owner, monkeypatch, personality="behavioral")
    answer = submit_answer(owner, interview_id, question_id, answer_text="I owned a release issue, coordinated the fix, and documented what I learned.").json()["data"]
    seen = {}

    class BehavioralGemini:
        def evaluate_interview_answer(self, **context):
            seen.update(context)
            return fake_evaluator().evaluate_interview_answer(**context)

    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: BehavioralGemini())
    response = client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    assert response.status_code == 200
    assert seen["personality"] == "behavioral"
    weak = heuristic_answer_evaluation(
        question="Tell me about a challenge.", question_type="behavioral", topic="", difficulty="medium",
        expected_skills=[], personality="behavioral", job_description="", resume_evidence="", answer_text="I don't know",
    )
    assert weak.overall_score <= 10


def test_answer_evaluation_enforces_owner_and_answer_interview_boundary(monkeypatch):
    owner = premium_token_for("evaluation-scope-owner@example.com", "Evaluation Scope Owner")
    other = premium_token_for("evaluation-scope-other@example.com", "Evaluation Scope Other")
    first_interview, first_question = create_interview_question(owner, monkeypatch)
    second_interview, _ = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, first_interview, first_question).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator())
    assert client.post(f"/api/v1/interviews/{second_interview}/answers/{answer['answer_id']}/evaluate", headers=owner).status_code == 404
    assert client.post(f"/api/v1/interviews/{first_interview}/answers/{answer['answer_id']}/evaluate", headers=other).status_code == 404


def test_answer_evaluation_falls_back_when_ai_output_is_invalid(monkeypatch):
    owner = premium_token_for("evaluation-fallback@example.com", "Evaluation Fallback")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]

    # Service-level fallback protects invalid Gemini results; exercise it
    # directly because routes depend on the service-layer contract.
    service = GeminiService()
    service._client = object()
    monkeypatch.setattr(service, "_evaluate_interview_answer_via_gemini", lambda **_: (_ for _ in ()).throw(ValueError("bad JSON")))
    fallback = service.evaluate_interview_answer(
        question="How would you design input validation?", question_type="technical", topic="Python",
        difficulty="medium", expected_skills=["Python"], personality="technical", job_description="",
        resume_evidence="", answer_text=answer["answer_text"],
    )
    assert fallback.feedback
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=60))
    assert client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner).status_code == 200


def test_fallback_evaluation_uses_question_intent_and_relevance_gates():
    question = "Walk me through a difficult bug or edge case in Python. How did you diagnose and fix it?"
    base = dict(
        question=question, question_type="technical", topic="Python", difficulty="medium",
        expected_skills=["Python"], personality="technical", job_description="", resume_evidence="",
    )
    strong = heuristic_answer_evaluation(
        **base,
        answer_text=("A missing input caused a Python error. I reproduced it with the failing value, traced the "
                     "values, and found an invalid assumption about missing fields. I added validation and a "
                     "safe fallback, then tested empty, invalid, and boundary inputs. I learned to check this path early."),
    )
    weak_relevant = heuristic_answer_evaluation(
        **base,
        answer_text="I had a Python wrong-output bug. I checked the code, found a bad condition, changed it, and retested.",
    )
    keyword_irrelevant = heuristic_answer_evaluation(
        **base,
        answer_text="I like Python because its syntax is simple, and I have learned Python, Java, C, C++, and SQL.",
    )
    unrelated = heuristic_answer_evaluation(**base, answer_text="sky is blue")
    unknown = heuristic_answer_evaluation(**base, answer_text="I don't know")

    assert strong.overall_score > weak_relevant.overall_score > keyword_irrelevant.overall_score
    assert keyword_irrelevant.overall_score <= 35
    assert unrelated.overall_score <= 20
    assert unknown.overall_score <= 10
    assert "diagnosed" in strong.feedback.lower() or "bug" in strong.feedback.lower()
    assert "does not answer the debugging question" in keyword_irrelevant.feedback.lower()
    assert "unsupported" not in strong.feedback.lower()
    assert any("bug or incorrect behavior" in item for item in strong.strengths)


def test_fallback_evaluation_uses_behavioral_components_and_penalizes_irrelevance():
    base = dict(
        question="Tell me about a setback in a project. What did you do and what did you learn?",
        question_type="behavioral", topic="", difficulty="medium", expected_skills=[], personality="friendly",
        job_description="", resume_evidence="",
    )
    strong = heuristic_answer_evaluation(
        **base,
        answer_text=("During a release, our team found a customer-facing issue before launch. I took ownership of "
                     "coordinating the fix and communicating the impact, and we resolved it before release. I learned "
                     "to add an earlier review checkpoint next time."),
    )
    weak = heuristic_answer_evaluation(**base, answer_text="I had a project deadline and I worked with the team to finish it.")
    irrelevant = heuristic_answer_evaluation(**base, answer_text="I enjoy Python because it is easy to read.")

    assert strong.overall_score > weak.overall_score > irrelevant.overall_score
    assert irrelevant.overall_score <= 20
    assert any("action" in item or "ownership" in item for item in strong.strengths)
    assert "does not answer the behavioral question" in irrelevant.feedback.lower()


def test_fallback_evaluation_handles_multi_intent_database_design_tradeoffs():
    base = dict(
        question=("In your Ride + Food Sharing Application | Python, HTML, JavaScript, how did you structure "
                  "the implementation around PostgreSQL? What trade-off did you make?"),
        question_type="project_deep_dive", topic="PostgreSQL", difficulty="medium", expected_skills=["PostgreSQL"],
        personality="technical", job_description="", resume_evidence="",
    )
    strong = heuristic_answer_evaluation(
        **base,
        answer_text=("PostgreSQL stores the structured application data while Python handles backend logic and HTML "
                     "and JavaScript render the interface. I separated database access from request handling and chose "
                     "a relational schema despite more upfront schema design. The benefit was better consistency and "
                     "easier relationship management, and I validated duplicate and invalid references."),
    )
    weak = heuristic_answer_evaluation(
        **base,
        answer_text=("I used PostgreSQL as the database. Python connected to it and I created tables and SQL queries. "
                     "PostgreSQL required more setup but stored data properly."),
    )
    keyword_irrelevant = heuristic_answer_evaluation(
        **base,
        answer_text="PostgreSQL is a popular relational database. I learned SQL and know Python, HTML, and JavaScript. I like Python.",
    )
    unrelated = heuristic_answer_evaluation(**base, answer_text="The sky is blue.")

    assert strong.overall_score > weak.overall_score > keyword_irrelevant.overall_score > unrelated.overall_score
    assert strong.overall_score - weak.overall_score >= 15
    assert weak.overall_score - keyword_irrelevant.overall_score >= 15
    assert strong.overall_score >= 75
    assert 40 <= weak.overall_score <= 60
    assert keyword_irrelevant.overall_score <= 25
    assert unrelated.overall_score <= 10
    assert "design choice" in strong.feedback.lower()
    assert "practical consequence or benefit" in strong.feedback.lower()
    assert "technologies generally" in keyword_irrelevant.feedback.lower() or "does not answer" in keyword_irrelevant.feedback.lower()


def test_fallback_evaluation_links_behavioral_collaboration_components_to_feedback_event():
    base = dict(
        question=("How did you work with others or gather feedback while building Core Computer Science: Data Structures "
                  "and Algorithms, Object-Oriented Programming, Database Management? What did that change?"),
        question_type="behavioral", topic="Database Management", difficulty="medium", expected_skills=[],
        personality="behavioral", job_description="", resume_evidence="",
    )
    strong = heuristic_answer_evaluation(
        **base,
        answer_text=("I discussed the database schema with my teammate, who noticed repeated data. We reviewed the "
                     "schema together, changed the design, updated the queries, and tested the revised structure. "
                     "That feedback improved the design and changed how I work now: I try to get feedback on my approach earlier."),
    )
    weak = heuristic_answer_evaluation(
        **base,
        answer_text="I worked with teammates, discussed solutions, received suggestions, made changes, and improved the final work.",
    )
    keyword_irrelevant = heuristic_answer_evaluation(
        **base,
        answer_text="I learned DSA, OOP, and DBMS, and they improved my programming knowledge.",
    )
    unrelated = heuristic_answer_evaluation(**base, answer_text="I enjoy watching movies with my friends on weekends.")

    assert strong.overall_score > weak.overall_score > keyword_irrelevant.overall_score >= unrelated.overall_score
    assert 75 <= strong.overall_score <= 90
    assert 40 <= weak.overall_score <= 60
    assert keyword_irrelevant.overall_score <= 25
    assert unrelated.overall_score <= 10
    assert any("future approach" in item for item in strong.strengths)
    assert not any("action" in item or "future approach" in item for item in unrelated.strengths)
    assert "collaboration and feedback question" in keyword_irrelevant.feedback.lower()


def test_fallback_evaluation_handles_friendly_decision_tradeoff_components():
    base = dict(
        question=("What guided your approach to Tools and Platforms: Git, GitHub, Vercel when you had to choose "
                  "between possible solutions?"),
        question_type="project_deep_dive", topic="Git", difficulty="medium", expected_skills=["Git", "GitHub", "Vercel"],
        personality="friendly", job_description="", resume_evidence="",
    )
    strong = heuristic_answer_evaluation(
        **base,
        answer_text=("When choosing between Git, GitHub, and Vercel, I first looked at the problem each tool needed "
                     "to solve rather than treating them as alternatives for the same purpose. I used Git for local version "
                     "control, GitHub for repository collaboration, and Vercel for a simple frontend deployment workflow. "
                     "The trade-off was convenience versus control: Vercel made deployment and updates simpler through GitHub "
                     "integration, while a more configurable hosting setup offered greater control. For this project scope, I "
                     "prioritized faster deployment and easier maintenance, so Vercel was the better fit."),
    )
    weak = heuristic_answer_evaluation(
        **base,
        answer_text=("I chose Git and GitHub because they made it easier to manage my code and versions. I used Vercel "
                     "for deployment because it was simple to use. I considered other ways of deploying the project, but "
                     "Vercel was easier, so I selected it."),
    )
    keyword_irrelevant = heuristic_answer_evaluation(
        **base,
        answer_text="Git is version control, GitHub stores repositories, and Vercel is a deployment platform.",
    )
    unrelated = heuristic_answer_evaluation(**base, answer_text="I enjoy movies and music on weekends.")

    assert strong.overall_score > weak.overall_score > keyword_irrelevant.overall_score > unrelated.overall_score
    assert 75 <= strong.overall_score <= 90
    assert 40 <= weak.overall_score <= 60
    assert keyword_irrelevant.overall_score <= 25
    assert unrelated.overall_score <= 10
    assert {"the alternatives considered", "the decision", "the reasoning or trade-off", "a practical benefit or consequence"} <= set(
        item.removeprefix("You explained ").rstrip(".") for item in strong.strengths
    )


def fake_gemini_full(*, overall=78, recommendation=RecommendationEnum.hire):
    """Combined fake covering both evaluate + summarize, for tests that call
    /evaluate and /complete under one monkeypatch of the same service module."""
    class FakeGemini:
        def evaluate_interview_answer(self, **context):
            return fake_evaluator(overall=overall).evaluate_interview_answer(**context)

        def generate_interview_summary(self, **context):
            return GeneratedInterviewSummary(
                summary="This session showed a solid grasp of the fundamentals with room to grow in edge cases.",
                recommendation=recommendation, key_strengths=["Directly answers the question."],
                key_gaps=["A concrete example"],
            )
    return FakeGemini()


def _fake_question_generator(contexts: list[dict]):
    class FakeGemini:
        def generate_interview_question(self, **context):
            contexts.append(context)
            return GeneratedQuestion(
                question=f"Adaptive question {context['question_number']}?", topic="Python",
                question_type="technical", difficulty=context["difficulty"],
                expected_skills=["Python"], reason="Adaptive test question.",
            )
    return FakeGemini()


# --------------------------------------------------------------------- #
# Confidence scoring
# --------------------------------------------------------------------- #
def test_answer_evaluation_includes_confidence_score_and_rationale_from_gemini(monkeypatch):
    owner = premium_token_for("confidence-gemini@example.com", "Confidence Gemini")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]

    class FakeGemini:
        def evaluate_interview_answer(self, **context):
            return GeneratedAnswerEvaluation(
                overall_score=80, relevance_score=80, correctness_score=75, depth_score=70, clarity_score=85,
                evidence_score=65, confidence_score=91, confidence_rationale="Decisive, specific phrasing.",
                strengths=["Directly answers the question."], weaknesses=["Could include an edge case."],
                missing_points=["A concrete example"], feedback=f"Evaluated {context['question_type']} answer.",
            )
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: FakeGemini())
    response = client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["confidence_score"] == 91
    assert data["confidence_rationale"] == "Decisive, specific phrasing."


def test_heuristic_confidence_penalizes_hedge_words():
    base = dict(
        question="Walk me through a difficult bug or edge case in Python. How did you diagnose and fix it?",
        question_type="technical", topic="Python", difficulty="medium", expected_skills=["Python"],
        personality="technical", job_description="", resume_evidence="",
    )
    decisive = heuristic_answer_evaluation(
        **base,
        answer_text=("A missing input caused a Python error. I reproduced it with the failing value, traced the "
                     "values, and found an invalid assumption about missing fields. I added validation and a "
                     "safe fallback, then tested empty, invalid, and boundary inputs. I learned to check this path early."),
    )
    hedged = heuristic_answer_evaluation(
        **base,
        answer_text=("I think maybe a missing input caused a Python error. I guess I probably reproduced it with "
                     "the failing value, and I'm not sure but perhaps traced the values to find what might have "
                     "been an invalid assumption about missing fields. I think I possibly added validation and a "
                     "fallback, then maybe tested some inputs. I guess I learned to check this path early."),
    )
    assert decisive.confidence_score > hedged.confidence_score


def test_heuristic_confidence_uses_duration_seconds():
    text = ("I reproduced the failing case, traced the values, found the invalid assumption, and fixed it with a "
            "validated fallback.")
    quick_score, _ = heuristic_confidence(answer_text=text, duration_seconds=5)
    unhurried_score, _ = heuristic_confidence(answer_text=text, duration_seconds=60)
    assert quick_score < unhurried_score


def test_confidence_is_capped_when_relevance_gate_triggers(monkeypatch):
    base = dict(
        question="Walk me through a difficult bug or edge case in Python. How did you diagnose and fix it?",
        question_type="technical", topic="Python", difficulty="medium", expected_skills=["Python"],
        personality="technical", job_description="", resume_evidence="",
    )
    irrelevant_answer = "I like Python because its syntax is simple, and I have learned Python, Java, C, C++, and SQL."
    fallback = heuristic_answer_evaluation(**base, answer_text=irrelevant_answer)

    service = GeminiService()
    service._client = object()
    overconfident = GeneratedAnswerEvaluation(
        overall_score=95, relevance_score=95, correctness_score=90, depth_score=90, clarity_score=95,
        evidence_score=90, confidence_score=95, confidence_rationale="Confident but off-topic.",
        strengths=["Fluent."], weaknesses=[], missing_points=[], feedback="Fluent but off-topic.",
    )
    monkeypatch.setattr(service, "_evaluate_interview_answer_via_gemini", lambda **_: overconfident)
    enforced = service.evaluate_interview_answer(**base, answer_text=irrelevant_answer)
    assert enforced.confidence_score == fallback.confidence_score
    assert enforced.confidence_score < 95


def test_evaluate_answer_passes_duration_seconds_to_gemini_service(monkeypatch):
    owner = premium_token_for("duration-passthrough@example.com", "Duration Passthrough")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id, duration_seconds=17).json()["data"]

    captured = {}

    class FakeGemini:
        def evaluate_interview_answer(self, **context):
            captured.update(context)
            return fake_evaluator().evaluate_interview_answer(**context)

    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: FakeGemini())
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    assert captured["duration_seconds"] == 17


# --------------------------------------------------------------------- #
# Adaptive questioning
# --------------------------------------------------------------------- #
def test_first_two_questions_use_baseline_difficulty_no_adaptation(monkeypatch):
    owner = premium_token_for("adaptive-baseline@example.com", "Adaptive Baseline")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]

    contexts: list[dict] = []
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: _fake_question_generator(contexts))
    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    assert contexts[0]["adaptation"] is None
    assert contexts[1]["adaptation"] is None


def test_third_question_receives_adaptation_context_from_prior_scores(monkeypatch):
    owner = premium_token_for("adaptive-low@example.com", "Adaptive Low")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]

    contexts: list[dict] = []
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: _fake_question_generator(contexts))
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=30))

    for _ in range(2):
        question = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner).json()["data"]
        answer = submit_answer(owner, interview_id, question["question_id"]).json()["data"]
        client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)

    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    adaptation = contexts[2]["adaptation"]
    assert adaptation is not None
    assert adaptation.average_score == 30
    assert adaptation.suggested_difficulty == DifficultyEnum.easy
    assert "Could include an edge case." in adaptation.recent_weaknesses
    assert "A concrete example" in adaptation.recent_missing_points


def test_adaptation_escalates_difficulty_after_strong_answers(monkeypatch):
    owner = premium_token_for("adaptive-high@example.com", "Adaptive High")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]

    contexts: list[dict] = []
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: _fake_question_generator(contexts))
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=90))

    for _ in range(2):
        question = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner).json()["data"]
        answer = submit_answer(owner, interview_id, question["question_id"]).json()["data"]
        client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)

    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    adaptation = contexts[2]["adaptation"]
    assert adaptation is not None
    assert adaptation.average_score == 90
    assert adaptation.suggested_difficulty == DifficultyEnum.hard


def test_adaptation_is_isolated_to_its_own_interview(monkeypatch):
    owner = premium_token_for("adaptive-isolated@example.com", "Adaptive Isolated")
    application_id = create_application(owner)

    interview_a = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]
    contexts_a: list[dict] = []
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: _fake_question_generator(contexts_a))
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=20))
    for _ in range(2):
        question = client.post(f"/api/v1/interviews/{interview_a}/questions", headers=owner).json()["data"]
        answer = submit_answer(owner, interview_a, question["question_id"]).json()["data"]
        client.post(f"/api/v1/interviews/{interview_a}/answers/{answer['answer_id']}/evaluate", headers=owner)

    interview_b = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]
    contexts_b: list[dict] = []
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: _fake_question_generator(contexts_b))
    for _ in range(3):
        client.post(f"/api/v1/interviews/{interview_b}/questions", headers=owner)
    assert contexts_b[2]["adaptation"] is None


def test_generate_question_works_without_request_body(monkeypatch):
    owner = premium_token_for("no-body@example.com", "No Body")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]

    class FakeGemini:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a rate limiter?", topic="Systems", question_type="technical",
                difficulty=DifficultyEnum.medium, expected_skills=["Systems"], reason="No-body regression test.",
            )
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    response = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    assert response.status_code == 200


# --------------------------------------------------------------------- #
# Session lifecycle
# --------------------------------------------------------------------- #
def test_interview_status_transitions_to_in_progress_and_sets_started_at(monkeypatch):
    owner = premium_token_for("lifecycle@example.com", "Lifecycle")
    interview_id, _ = create_interview_question(owner, monkeypatch)
    session = client.get(f"/api/v1/interviews/{interview_id}", headers=owner).json()["data"]
    assert session["status"] == "in_progress"
    started_at = session["started_at"]
    assert started_at is not None

    class FakeGemini:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a cache eviction policy?", topic="Systems", question_type="technical",
                difficulty=DifficultyEnum.medium, expected_skills=["Systems"], reason="Second question.",
            )
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    session_after = client.get(f"/api/v1/interviews/{interview_id}", headers=owner).json()["data"]
    assert session_after["started_at"] == started_at


def test_generate_question_rejected_after_completion(monkeypatch):
    owner = premium_token_for("complete-block@example.com", "Complete Block")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_gemini_full())
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    completed = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    assert completed.status_code == 200

    response = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    assert response.status_code == 409


# --------------------------------------------------------------------- #
# History list
# --------------------------------------------------------------------- #
def test_list_interviews_is_owner_scoped_and_paginated(monkeypatch):
    owner = premium_token_for("history-owner@example.com", "History Owner")
    other = premium_token_for("history-other@example.com", "History Other")
    app1 = create_application(owner)
    app2 = create_application(owner)
    interview1 = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": app1, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]
    interview2 = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": app2, "personality": "friendly", "difficulty": "easy"},
    ).json()["data"]["interview_id"]
    other_app = create_application(other)
    client.post(
        "/api/v1/interviews", headers=other,
        json={"application_id": other_app, "personality": "technical", "difficulty": "medium"},
    )

    page1 = client.get("/api/v1/interviews", headers=owner, params={"page": 1, "page_size": 1}).json()["data"]
    assert page1["total"] == 2
    assert len(page1["items"]) == 1
    page2 = client.get("/api/v1/interviews", headers=owner, params={"page": 2, "page_size": 1}).json()["data"]
    assert len(page2["items"]) == 1
    seen_ids = {page1["items"][0]["interview_id"], page2["items"][0]["interview_id"]}
    assert seen_ids == {interview1, interview2}

    other_listed = client.get("/api/v1/interviews", headers=other).json()["data"]
    assert other_listed["total"] == 1
    assert all(item["interview_id"] != interview1 for item in other_listed["items"])


def test_list_interviews_filters_by_application_id(monkeypatch):
    owner = premium_token_for("history-filter@example.com", "History Filter")
    app1 = create_application(owner)
    app2 = create_application(owner)
    interview1 = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": app1, "personality": "technical", "difficulty": "medium"},
    ).json()["data"]["interview_id"]
    client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": app2, "personality": "technical", "difficulty": "medium"},
    )

    filtered = client.get("/api/v1/interviews", headers=owner, params={"application_id": app1}).json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["interview_id"] == interview1


def test_list_interviews_computes_average_score_without_denormalized_storage(monkeypatch):
    owner = premium_token_for("history-avg@example.com", "History Avg")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer1 = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=80))
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer1['answer_id']}/evaluate", headers=owner)

    class FakeGeminiQ2:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a URL shortener?", topic="Systems", question_type="technical",
                difficulty=DifficultyEnum.medium, expected_skills=["Systems"], reason="Second question.",
            )
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGeminiQ2())
    question2 = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner).json()["data"]
    answer2 = submit_answer(owner, interview_id, question2["question_id"]).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=60))
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer2['answer_id']}/evaluate", headers=owner)

    application_id = client.get(f"/api/v1/interviews/{interview_id}", headers=owner).json()["data"]["application_id"]
    listed = client.get("/api/v1/interviews", headers=owner, params={"application_id": application_id}).json()["data"]
    item = next(i for i in listed["items"] if i["interview_id"] == interview_id)
    assert item["answered_count"] == 2
    assert item["average_score"] == 70.0
    assert item["average_confidence"] == 72.0


# --------------------------------------------------------------------- #
# Full nested session fetch
# --------------------------------------------------------------------- #
def test_get_interview_full_returns_ordered_nested_tree_with_unanswered_questions(monkeypatch):
    owner = premium_token_for("full-tree@example.com", "Full Tree")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=88))
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)

    class FakeGeminiQ2:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a notification service?", topic="Systems", question_type="technical",
                difficulty=DifficultyEnum.medium, expected_skills=["Systems"], reason="Second question.",
            )
    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGeminiQ2())
    client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)  # left unanswered

    full = client.get(f"/api/v1/interviews/{interview_id}/full", headers=owner).json()["data"]
    assert [item["question"]["question_number"] for item in full["items"]] == [1, 2]
    assert full["items"][0]["answer"] is not None
    assert full["items"][0]["evaluation"]["overall_score"] == 88
    assert full["items"][1]["answer"] is None
    assert full["items"][1]["evaluation"] is None
    assert full["average_score"] == 88


def test_get_interview_full_is_owner_scoped(monkeypatch):
    owner = premium_token_for("full-scope-owner@example.com", "Full Scope Owner")
    other = premium_token_for("full-scope-other@example.com", "Full Scope Other")
    interview_id, _ = create_interview_question(owner, monkeypatch)
    assert client.get(f"/api/v1/interviews/{interview_id}/full", headers=owner).status_code == 200
    assert client.get(f"/api/v1/interviews/{interview_id}/full", headers=other).status_code == 404


# --------------------------------------------------------------------- #
# Session completion
# --------------------------------------------------------------------- #
def test_complete_interview_computes_aggregates_and_persists_summary(monkeypatch):
    owner = premium_token_for("complete-aggregate@example.com", "Complete Aggregate")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]

    class FakeGemini:
        def evaluate_interview_answer(self, **context):
            return GeneratedAnswerEvaluation(
                overall_score=80, relevance_score=85, correctness_score=80, depth_score=75, clarity_score=85,
                evidence_score=70, confidence_score=72, confidence_rationale="Decisive phrasing.",
                strengths=["Clear reasoning."], weaknesses=["Could add an edge case."], missing_points=["A metric"],
                feedback="Solid answer.",
            )

        def generate_interview_summary(self, **context):
            return GeneratedInterviewSummary(
                summary="This candidate demonstrated solid technical reasoning throughout the session.",
                recommendation=RecommendationEnum.hire, key_strengths=["Clear reasoning."], key_gaps=["A metric"],
            )
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: FakeGemini())
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)

    completed = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    assert completed.status_code == 200
    data = completed.json()["data"]
    assert data["status"] == "completed"
    assert data["answered_count"] == 1
    assert data["average_score"] == 80
    assert data["average_confidence"] == 72
    assert data["recommendation"] == "hire"
    assert "technical reasoning" in data["summary"]

    full = client.get(f"/api/v1/interviews/{interview_id}/full", headers=owner).json()["data"]
    assert full["status"] == "completed"
    assert full["recommendation"] == "hire"
    assert full["average_score"] == 80


def test_complete_interview_uses_heuristic_summary_when_gemini_disabled(monkeypatch):
    owner = premium_token_for("complete-heuristic@example.com", "Complete Heuristic")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id, answer_text="I don't know").json()["data"]

    disabled_service = GeminiService()
    disabled_service._client = None
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: disabled_service)
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)

    completed = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    assert completed.status_code == 200
    data = completed.json()["data"]
    assert data["answered_count"] == 1
    assert data["recommendation"] == "no_hire"
    assert data["summary"]


def test_complete_interview_is_idempotent_guard(monkeypatch):
    owner = premium_token_for("complete-guard@example.com", "Complete Guard")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_gemini_full())
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    first = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    second = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    assert first.status_code == 200
    assert second.status_code == 409


def test_complete_interview_with_zero_answered_questions(monkeypatch):
    owner = premium_token_for("complete-zero@example.com", "Complete Zero")
    interview_id, _ = create_interview_question(owner, monkeypatch)
    disabled_service = GeminiService()
    disabled_service._client = None
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: disabled_service)

    completed = client.post(f"/api/v1/interviews/{interview_id}/complete", headers=owner)
    assert completed.status_code == 200
    data = completed.json()["data"]
    assert data["answered_count"] == 0
    assert data["average_score"] is None
    assert data["average_confidence"] is None
    assert data["recommendation"] == "no_hire"
    assert data["summary"]


def test_complete_interview_is_owner_scoped(monkeypatch):
    owner = premium_token_for("complete-scope-owner@example.com", "Complete Scope Owner")
    other = premium_token_for("complete-scope-other@example.com", "Complete Scope Other")
    interview_id, question_id = create_interview_question(owner, monkeypatch)
    answer = submit_answer(owner, interview_id, question_id).json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_gemini_full())
    client.post(f"/api/v1/interviews/{interview_id}/answers/{answer['answer_id']}/evaluate", headers=owner)
    assert client.post(f"/api/v1/interviews/{interview_id}/complete", headers=other).status_code == 404


def test_question_target_is_selectable_and_capped_at_six():
    owner = premium_token_for("target-cap@example.com", "Target Cap")
    application_id = create_application(owner)

    within_range = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium", "question_target": 3},
    )
    assert within_range.status_code == 200
    assert within_range.json()["data"]["question_target"] == 3

    too_many = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium", "question_target": 7},
    )
    assert too_many.status_code == 422


def test_generate_question_rejected_once_target_reached(monkeypatch):
    owner = premium_token_for("target-reached@example.com", "Target Reached")
    application_id = create_application(owner)
    interview_id = client.post(
        "/api/v1/interviews", headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium", "question_target": 1},
    ).json()["data"]["interview_id"]

    class FakeGemini:
        def generate_interview_question(self, **_context):
            return GeneratedQuestion(
                question="How would you design a rate limiter?", topic="Systems", question_type="technical",
                difficulty=DifficultyEnum.medium, expected_skills=["Systems"], reason="Tests the question cap.",
            )

    monkeypatch.setattr("app.services.interview_questions.get_gemini_service", lambda: FakeGemini())
    first = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    assert first.status_code == 200
    second = client.post(f"/api/v1/interviews/{interview_id}/questions", headers=owner)
    assert second.status_code == 409


def test_resubmitting_an_answer_updates_in_place_and_does_not_inflate_answered_count(monkeypatch):
    owner = premium_token_for("resubmit-progress@example.com", "Resubmit Progress")
    interview_id, question_id = create_interview_question(owner, monkeypatch)

    first_answer = submit_answer(owner, interview_id, question_id, answer_text="First draft answer.").json()["data"]
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator(overall=40))
    client.post(f"/api/v1/interviews/{interview_id}/answers/{first_answer['answer_id']}/evaluate", headers=owner)

    second_answer = submit_answer(owner, interview_id, question_id, answer_text="Revised, more detailed answer.").json()["data"]
    assert second_answer["answer_id"] == first_answer["answer_id"]

    full = client.get(f"/api/v1/interviews/{interview_id}/full", headers=owner).json()["data"]
    assert len(full["items"]) == 1
    assert full["items"][0]["answer"]["answer_text"] == "Revised, more detailed answer."
    # The stale evaluation from the first draft must not survive the resubmission.
    assert full["items"][0]["evaluation"] is None

    application_id = client.get(f"/api/v1/interviews/{interview_id}", headers=owner).json()["data"]["application_id"]
    listed = client.get("/api/v1/interviews", headers=owner, params={"application_id": application_id}).json()["data"]
    item = next(i for i in listed["items"] if i["interview_id"] == interview_id)
    assert item["question_count"] == 1
    assert item["answered_count"] == 0


def test_delete_interview_removes_it_and_is_owner_scoped(monkeypatch):
    owner = premium_token_for("delete-owner@example.com", "Delete Owner")
    other = premium_token_for("delete-other@example.com", "Delete Other")
    interview_id, _ = create_interview_question(owner, monkeypatch)

    assert client.delete(f"/api/v1/interviews/{interview_id}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/interviews/{interview_id}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=owner).status_code == 404
