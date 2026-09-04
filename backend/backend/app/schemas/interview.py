from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


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


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class APIResponse(BaseModel):
    success: bool
    data: InterviewData | None = None
    error: ErrorDetail | None = None
