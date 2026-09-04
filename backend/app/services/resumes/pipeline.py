"""Shared resume ingest/analysis pipeline.

The five `/resumes/*` endpoints are a frozen contract, but the FREE-tier
quick scan needs exactly the same work done against an internally managed
application. Rather than duplicating the handlers, the two multi-step
operations live here and both routers call them. Any change to scoring,
storage or versioning therefore lands in both surfaces at once.

Callers are responsible for authorization; these functions assume the
application has already been confirmed to belong to the current user.
"""
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.resume import AtsReport, Resume
from app.schemas.resume import (
    AnalyzeResumeResponse,
    ParsedResumeData,
    ResumeDetails,
    UploadResumeResponse,
)
from app.services.resumes.ats_engine import (
    calculate_ats_score,
    calculate_match_score,
    generate_suggestions,
)
from app.services.resumes.exceptions import (
    FileTooLargeError,
    InvalidRequestError,
    ResumeNotFoundError,
)
from app.services.resumes.extraction import extract_jd_file, extract_jd_text, extract_text
from app.services.resumes.gemini_service import get_gemini_service
from app.services.resumes.storage import get_storage_backend, new_resume_id
from app.services.resumes.versioning import next_version_number

settings = get_settings()


def public_resume_details(parsed: ParsedResumeData) -> ResumeDetails:
    """The single choke point for resume data leaving the server.

    Identity and contact fields (candidate_name, email, phone) stay in the
    protected record; only career content is exposed.
    """
    return ResumeDetails(
        skills=parsed.skills,
        experience_years=parsed.experience_years,
        work_history=parsed.work_history,
        education=parsed.education,
    )


def public_file_reference(resume_id: str) -> str:
    """Opaque stand-in for the private storage locator.

    `Resume.file_url` holds a filesystem path (or bucket key); returning it
    would disclose server layout and give a caller something to probe. There
    is no download endpoint, so no client needs the real value.
    """
    return f"resume://{resume_id}"


async def ingest_resume(
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    application_id: str,
    db: AsyncSession,
) -> tuple[Resume, UploadResumeResponse]:
    """Validate, extract, parse, store and version an uploaded resume."""
    if len(file_bytes) > settings.max_upload_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_mb}MB upload limit.")
    if len(file_bytes) == 0:
        raise InvalidRequestError("Uploaded file is empty.")

    raw_text = extract_text(file_bytes, filename, content_type)
    parsed = get_gemini_service().parse_resume(raw_text)

    resume_id = new_resume_id()
    ext = ".pdf" if filename.lower().endswith(".pdf") else ".docx"
    file_url = await get_storage_backend().save(file_bytes, ext, resume_id)

    version_number = await next_version_number(db, application_id)

    resume = Resume(
        id=resume_id,
        application_id=application_id,
        version_number=version_number,
        file_url=file_url,
        raw_text=raw_text,
        parsed_data=parsed.model_dump(),
        is_best_version=(version_number == 1),  # first version defaults to "best" until compared
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    payload = UploadResumeResponse(
        resume_id=resume.id,
        application_id=resume.application_id,
        version_number=resume.version_number,
        parsed_data=public_resume_details(parsed),
    )
    return resume, payload


async def run_analysis(
    *,
    resume: Resume,
    application_id: str,
    jd_content: str,
    db: AsyncSession,
) -> tuple[AtsReport, AnalyzeResumeResponse]:
    """Score a stored resume against a job description and persist the report."""
    jd_parsed = get_gemini_service().parse_jd(jd_content)
    resume_parsed = ParsedResumeData.model_validate(resume.parsed_data)

    ats_score, ats_components = calculate_ats_score(
        resume.raw_text, resume_parsed, jd_parsed, jd_content
    )
    match_score, matched_skills, missing_skills, match_components = calculate_match_score(
        resume_parsed, jd_parsed
    )
    suggestions = generate_suggestions(resume_parsed, jd_parsed, missing_skills, ats_components)

    report = AtsReport(
        resume_id=resume.id,
        application_id=application_id,
        ats_score=ats_score,
        match_score=match_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        improvement_suggestions=[s.model_dump() for s in suggestions],
        score_breakdown={"ats": ats_components, "match": match_components},
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    payload = AnalyzeResumeResponse(
        report_id=report.id,
        application_id=application_id,
        resume_id=resume.id,
        ats_score=report.ats_score,
        match_score=report.match_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        improvement_suggestions=suggestions,
        jd_details=jd_parsed,
        ats_breakdown=ats_components,
        match_breakdown=match_components,
    )
    return report, payload


# ---------------------------------------------------------------------------
# Shared request helpers
#
# These live here rather than in a router so that /resumes and /quick-scan
# raise identical errors with identical codes for identical inputs.
# ---------------------------------------------------------------------------
def validate_uuid(value: str, field_name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise InvalidRequestError(f"'{field_name}' must be a valid UUID.")


async def get_resume_or_404(db: AsyncSession, resume_id: str) -> Resume:
    resume_id = validate_uuid(resume_id, "resume_id")
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if resume is None:
        raise ResumeNotFoundError(f"No resume found with id '{resume_id}'.")
    return resume


async def resolve_jd_content(jd_file: UploadFile | None, jd_text: str | None) -> str:
    """Accept a job description as either an uploaded file or pasted text."""
    if jd_file is not None:
        jd_bytes = await jd_file.read()
        if len(jd_bytes) > settings.max_upload_bytes:
            raise FileTooLargeError(f"JD file exceeds the {settings.max_upload_mb}MB upload limit.")
        if len(jd_bytes) == 0:
            raise InvalidRequestError("Uploaded JD file is empty.")
        return extract_jd_file(jd_bytes, jd_file.filename or "", jd_file.content_type)
    if jd_text and jd_text.strip():
        if len(jd_text.encode("utf-8")) > settings.max_upload_bytes:
            raise FileTooLargeError(
                f"Job description exceeds the {settings.max_upload_mb}MB upload limit."
            )
        return extract_jd_text(jd_text)
    raise InvalidRequestError("Provide a job description as text or a file.")
