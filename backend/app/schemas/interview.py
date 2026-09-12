from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PersonalityEnum(str, Enum):
    technical = "technical"
    friendly = "friendly"
    strict = "strict"
    behavioral = "behavioral"
    mixed = "mixed"


class DifficultyEnum(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AnswerSourceEnum(str, Enum):
    typed = "typed"
    voice = "voice"


class RecommendationEnum(str, Enum):
    strong_hire = "strong_hire"
    hire = "hire"
    borderline = "borderline"
    no_hire = "no_hire"


MAX_INTERVIEW_QUESTIONS = 6


class InterviewCreateRequest(BaseModel):
    application_id: UUID
    personality: PersonalityEnum
    difficulty: DifficultyEnum
    question_target: int = Field(default=5, ge=1, le=MAX_INTERVIEW_QUESTIONS)


class InterviewData(BaseModel):
    interview_id: UUID
    application_id: UUID
    personality: str
    difficulty: str
    status: str
    question_count: int = 0
    question_target: int
    started_at: datetime | None = None


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=10, max_length=2000)
    topic: str = Field(min_length=1, max_length=160)
    question_type: str = Field(min_length=1, max_length=80)
    difficulty: DifficultyEnum
    expected_skills: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(min_length=5, max_length=1000)


class InterviewQuestionData(GeneratedQuestion):
    question_id: UUID
    interview_id: UUID
    question_number: int


class InterviewQuestionsData(BaseModel):
    interview_id: UUID
    questions: list[InterviewQuestionData]


class AnswerSubmitRequest(BaseModel):
    question_id: UUID
    answer_text: str = Field(min_length=1, max_length=12000)
    source: AnswerSourceEnum = AnswerSourceEnum.typed
    duration_seconds: float | None = Field(default=None, ge=0, le=14400)

    @field_validator("answer_text")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer_text must not be empty")
        return value.strip()


class GeneratedAnswerEvaluation(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    relevance_score: int = Field(ge=0, le=100)
    correctness_score: int = Field(ge=0, le=100)
    depth_score: int = Field(ge=0, le=100)
    clarity_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    confidence_rationale: str = Field(min_length=3, max_length=400)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    weaknesses: list[str] = Field(default_factory=list, max_length=8)
    missing_points: list[str] = Field(default_factory=list, max_length=8)
    feedback: str = Field(min_length=5, max_length=2000)


class InterviewAnswerData(BaseModel):
    answer_id: UUID
    interview_id: UUID
    question_id: UUID
    answer_text: str
    source: AnswerSourceEnum
    duration_seconds: float | None = None
    audio_mime_type: str | None = None
    audio_size_bytes: int | None = None
    submitted_at: datetime


class InterviewAnswerEvaluationData(GeneratedAnswerEvaluation):
    evaluation_id: UUID
    answer_id: UUID
    evaluated_at: datetime
    # Contract-compatible summaries of the persisted rubric dimensions.
    technical_correctness: int
    relevance: int
    reasoning: int
    communication: int


class InterviewSummaryData(BaseModel):
    """One row in the paginated history list — computed at read time, nothing denormalized."""

    interview_id: UUID
    application_id: UUID
    personality: str
    difficulty: str
    status: str
    question_count: int
    question_target: int
    answered_count: int
    average_score: float | None = None
    average_confidence: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    recommendation: str | None = None


class InterviewHistoryData(BaseModel):
    items: list[InterviewSummaryData]
    total: int
    page: int
    page_size: int


class InterviewQuestionWithAnswerData(BaseModel):
    question: InterviewQuestionData
    answer: InterviewAnswerData | None = None
    evaluation: InterviewAnswerEvaluationData | None = None


class InterviewFullSessionData(BaseModel):
    interview_id: UUID
    application_id: UUID
    personality: str
    difficulty: str
    status: str
    question_target: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    summary: str | None = None
    recommendation: str | None = None
    average_score: float | None = None
    average_confidence: float | None = None
    items: list[InterviewQuestionWithAnswerData]


class GeneratedInterviewSummary(BaseModel):
    """Gemini structured-output contract for session completion."""

    summary: str = Field(min_length=20, max_length=2000)
    recommendation: RecommendationEnum
    key_strengths: list[str] = Field(default_factory=list, max_length=6)
    key_gaps: list[str] = Field(default_factory=list, max_length=6)


class CompleteInterviewData(BaseModel):
    interview_id: UUID
    status: str
    completed_at: datetime
    question_count: int
    answered_count: int
    average_score: float | None = None
    average_confidence: float | None = None
    summary: str
    recommendation: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIResponse(BaseModel):
    success: bool
    data: (
        InterviewData
        | InterviewQuestionData
        | InterviewQuestionsData
        | InterviewAnswerData
        | InterviewAnswerEvaluationData
        | InterviewHistoryData
        | InterviewFullSessionData
        | CompleteInterviewData
        | None
    ) = None
    error: ErrorDetail | None = None
