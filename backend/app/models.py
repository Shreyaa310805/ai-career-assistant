"""
SQLAlchemy ORM models for Module 1, matching the schema fixed in ISSUE-03:

    resumes(id, application_id, version_number, file_url, raw_text,
            parsed_data, is_best_version, created_at)
    ats_reports(id, resume_id, application_id, ats_score, match_score,
                matched_skills, missing_skills, improvement_suggestions,
                created_at)

`PortableJSON` renders as native JSONB on Postgres and as JSON (TEXT-backed)
on SQLite, so the exact same models back both the standalone SQLite mode
and a real Postgres/Supabase deployment without any migration changes.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import JSON, CHAR, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class GUID(TypeDecorator):
    """Platform-independent UUID: native UUID on Postgres, CHAR(36) on SQLite."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


class PortableJSON(TypeDecorator):
    """JSONB on Postgres, JSON (TEXT) on everything else (SQLite for tests/
    standalone mode)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid_str)
    application_id: Mapped[str] = mapped_column(GUID(), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    file_url: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[dict] = mapped_column(PortableJSON, nullable=False)
    is_best_version: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    ats_reports: Mapped[list["AtsReport"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class AtsReport(Base):
    __tablename__ = "ats_reports"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=_uuid_str)
    resume_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[str] = mapped_column(GUID(), nullable=False, index=True)
    ats_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    matched_skills: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    missing_skills: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    improvement_suggestions: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    resume: Mapped["Resume"] = relationship(back_populates="ats_reports")
