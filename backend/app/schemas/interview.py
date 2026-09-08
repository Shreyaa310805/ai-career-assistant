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


class InterviewModeEnum(str, Enum):
    standard = "standard"
    adaptive = "adaptive"


class AnswerSourceEnum(str, Enum):
    typed = "typed"
    voice = "voice"


class InterviewCreateRequest(BaseModel):
    application_id: UUID
    personality: PersonalityEnum
    difficulty: DifficultyEnum


class InterviewData(BaseModel):
    interview_id: UUID
    application_id: UUID
    personality: str
    difficulty: str
    status: str
    question_count: int = 0
    started_at: datetime | None = None


class GenerateQuestionRequest(BaseModel):
    mode: InterviewModeEnum = InterviewModeEnum.standard


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


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIResponse(BaseModel):
    success: bool
    data: InterviewData | InterviewQuestionData | InterviewQuestionsData | InterviewAnswerData | InterviewAnswerEvaluationData | None = None
    error: ErrorDetail | None = None
