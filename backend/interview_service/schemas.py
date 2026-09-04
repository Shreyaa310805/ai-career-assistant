import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Any
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
    application_id: uuid.UUID
    personality: PersonalityEnum
    difficulty: DifficultyEnum


class InterviewData(BaseModel):
    interview_id: uuid.UUID
    application_id: uuid.UUID
    personality: str
    difficulty: str
    status: str
    question_count: int = 0
    started_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None