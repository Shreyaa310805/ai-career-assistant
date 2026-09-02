from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=160)
    status: ApplicationStatus = ApplicationStatus.SAVED
    location: str | None = Field(default=None, max_length=160)
    job_url: HttpUrl | None = None
    job_description: str | None = Field(default=None, max_length=20000)
    applied_at: date | None = None

    @field_validator("company", "role")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class ApplicationUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, min_length=1, max_length=160)
    status: ApplicationStatus | None = None
    location: str | None = Field(default=None, max_length=160)
    job_url: HttpUrl | None = None
    job_description: str | None = Field(default=None, max_length=20000)
    applied_at: date | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company: str
    role: str
    status: ApplicationStatus
    location: str | None
    job_url: str | None
    job_description: str | None
    applied_at: date | None
    created_at: datetime
    updated_at: datetime


class DashboardSummary(BaseModel):
    total: int
    saved: int
    applied: int
    interviewing: int
    offer: int
    rejected: int
    recent_applications: list[ApplicationResponse]
