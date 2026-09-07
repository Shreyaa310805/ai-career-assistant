from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIResponse(BaseModel):
    success: bool
    data: InterviewData | InterviewQuestionData | InterviewQuestionsData | None = None
    error: ErrorDetail | None = None
