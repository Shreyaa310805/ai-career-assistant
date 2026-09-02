"""
Module 1 (Resume & ATS) route handlers — implements exactly the five
endpoints in the frozen API contract:

    POST  /api/v1/resumes/upload
    POST  /api/v1/resumes/analyze
    GET   /api/v1/resumes/versions/{application_id}
    POST  /api/v1/resumes/compare
    PATCH /api/v1/resumes/select-best

Every handler returns via success_response() (the {success,data,error}
envelope); every failure raises an ApiError subclass that the global
exception handler in app/main.py converts to the same envelope.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.application import Application

from app.core.config import get_settings
from app.db.resume_session import get_db
from app.services.resumes.exceptions import (
    ApplicationMismatchError,
    FileTooLargeError,
    InvalidRequestError,
    ResumeNotFoundError,
)
from app.models.resume import AtsReport, Resume
from app.services.resumes.response import success_response
from app.schemas.resume import (
    AnalyzeResumeResponse,
    CompareRequest,
    CompareResumesResponse,
    LatestAtsSummary,
    ParsedResumeData,
    ResumeVersionSummary,
    ResumeDetails,
    SelectBestRequest,
    SelectBestResponse,
    UploadResumeResponse,
    VersionListResponse,
)
from app.services.resumes.ats_engine import calculate_ats_score, calculate_match_score, generate_suggestions
from app.services.resumes.extraction import extract_jd_file, extract_jd_text, extract_text
from app.services.resumes.gemini_service import get_gemini_service
from app.services.resumes.storage import get_storage_backend, new_resume_id
from app.services.resumes.versioning import diff_versions, get_latest_ats_report, next_version_number, recommend_version

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()


def _public_resume_details(parsed: ParsedResumeData) -> ResumeDetails:
    """Do not return contact/identity data extracted from a resume."""
    return ResumeDetails(
        skills=parsed.skills,
        experience_years=parsed.experience_years,
        work_history=parsed.work_history,
        education=parsed.education,
    )


def _validate_uuid(value: str, field_name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise InvalidRequestError(f"'{field_name}' must be a valid UUID.")


def _require_owned_application(application_id: str, current_user: CurrentUser, db: DbSession) -> None:
    """Bind resume records to an application owned by the current user."""
    application = db.get(Application, uuid.UUID(application_id))
    if application is None:
        # Keep the response deliberately non-specific, matching application routes.
        raise ResumeNotFoundError("No application found for this resume operation.")
    if application.user_id != current_user.id:
        raise ResumeNotFoundError("No application found for this resume operation.")


async def _get_resume_or_404(db: AsyncSession, resume_id: str) -> Resume:
    resume_id = _validate_uuid(resume_id, "resume_id")
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if resume is None:
        raise ResumeNotFoundError(f"No resume found with id '{resume_id}'.")
    return resume


def _resume_to_summary(resume: Resume, latest_report: AtsReport | None) -> ResumeVersionSummary:
    return ResumeVersionSummary(
        resume_id=resume.id,
        application_id=resume.application_id,
        version_number=resume.version_number,
        file_url=resume.file_url,
        is_best_version=resume.is_best_version,
        created_at=resume.created_at,
        parsed_data=_public_resume_details(ParsedResumeData.model_validate(resume.parsed_data)),
        latest_ats_report=(
            LatestAtsSummary(
                report_id=latest_report.id,
                ats_score=latest_report.ats_score,
                match_score=latest_report.match_score,
                created_at=latest_report.created_at,
            )
            if latest_report is not None
            else None
        ),
    )


# --------------------------------------------------------------------------
# 1. POST /resumes/upload — ISSUE-10 / ISSUE-11
# --------------------------------------------------------------------------
@router.post("/upload")
async def upload_resume(
    current_user: CurrentUser,
    application_db: DbSession,
    file: UploadFile = File(...),
    application_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    application_id = _validate_uuid(application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"File exceeds the {settings.max_upload_mb}MB upload limit."
        )
    if len(file_bytes) == 0:
        raise InvalidRequestError("Uploaded file is empty.")

    raw_text = extract_text(file_bytes, file.filename or "", file.content_type)

    gemini = get_gemini_service()
    parsed = gemini.parse_resume(raw_text)

    resume_id = new_resume_id()
    ext = ".pdf" if (file.filename or "").lower().endswith(".pdf") else ".docx"
    storage = get_storage_backend()
    file_url = await storage.save(file_bytes, ext, resume_id)

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
        parsed_data=_public_resume_details(parsed),
    )
    return success_response(payload.model_dump(mode="json"))


# --------------------------------------------------------------------------
# 2. POST /resumes/analyze — ISSUE-12 / ISSUE-13 / ISSUE-14 / ISSUE-15 / ISSUE-16
# --------------------------------------------------------------------------
@router.post("/analyze")
async def analyze_resume(
    current_user: CurrentUser,
    application_db: DbSession,
    jd_file: UploadFile | None = File(None),
    jd_text: str | None = Form(None),
    application_id: str = Form(...),
    resume_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    application_id = _validate_uuid(application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)
    resume = await _get_resume_or_404(db, resume_id)

    if resume.application_id != application_id:
        raise ApplicationMismatchError(
            "resume_id does not belong to the given application_id."
        )

    if jd_file is not None:
        jd_bytes = await jd_file.read()
        if len(jd_bytes) > settings.max_upload_bytes:
            raise FileTooLargeError(
                f"JD file exceeds the {settings.max_upload_mb}MB upload limit."
            )
        if len(jd_bytes) == 0:
            raise InvalidRequestError("Uploaded JD file is empty.")
        jd_content = extract_jd_file(jd_bytes, jd_file.filename or "", jd_file.content_type)
    elif jd_text and jd_text.strip():
        if len(jd_text.encode("utf-8")) > settings.max_upload_bytes:
            raise FileTooLargeError(
                f"Job description exceeds the {settings.max_upload_mb}MB upload limit."
            )
        jd_content = extract_jd_text(jd_text)
    else:
        raise InvalidRequestError("Provide a job description as text or a file.")

    gemini = get_gemini_service()
    jd_parsed = gemini.parse_jd(jd_content)
    resume_parsed = ParsedResumeData.model_validate(resume.parsed_data)

    ats_score, ats_components = calculate_ats_score(resume.raw_text, resume_parsed)
    match_score, matched_skills, missing_skills, _match_components = calculate_match_score(
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
    )
    return success_response(payload.model_dump(mode="json"))


# --------------------------------------------------------------------------
# 3. GET /resumes/versions/{application_id} — ISSUE-17
# --------------------------------------------------------------------------
@router.get("/versions/{application_id}")
async def list_versions(
    application_id: str,
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    application_id = _validate_uuid(application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)

    result = await db.execute(
        select(Resume)
        .where(Resume.application_id == application_id)
        .order_by(Resume.version_number.asc())
    )
    resumes = result.scalars().all()

    summaries = []
    for resume in resumes:
        latest_report = await get_latest_ats_report(db, resume.id)
        summaries.append(_resume_to_summary(resume, latest_report))

    payload = VersionListResponse(application_id=application_id, versions=summaries)
    return success_response(payload.model_dump(mode="json"))


# --------------------------------------------------------------------------
# 4. POST /resumes/compare — ISSUE-18
# --------------------------------------------------------------------------
@router.post("/compare")
async def compare_resumes(
    body: CompareRequest,
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    resume_v1 = await _get_resume_or_404(db, body.resume_id_v1)
    resume_v2 = await _get_resume_or_404(db, body.resume_id_v2)

    if resume_v1.application_id != resume_v2.application_id:
        raise ApplicationMismatchError(
            "resume_id_v1 and resume_id_v2 must belong to the same application_id."
        )
    _require_owned_application(resume_v1.application_id, current_user, application_db)

    parsed_v1 = ParsedResumeData.model_validate(resume_v1.parsed_data)
    parsed_v2 = ParsedResumeData.model_validate(resume_v2.parsed_data)

    ats_v1 = await get_latest_ats_report(db, resume_v1.id)
    ats_v2 = await get_latest_ats_report(db, resume_v2.id)

    diff = diff_versions(parsed_v1, parsed_v2, ats_v1, ats_v2)
    recommended, reason = recommend_version(diff, ats_v1, ats_v2)

    payload = CompareResumesResponse(
        resume_v1=_resume_to_summary(resume_v1, ats_v1),
        resume_v2=_resume_to_summary(resume_v2, ats_v2),
        diff=diff,
        recommended_version=recommended,
        recommendation_reason=reason,
    )
    return success_response(payload.model_dump(mode="json"))


# --------------------------------------------------------------------------
# 5. PATCH /resumes/select-best — ISSUE-19
# --------------------------------------------------------------------------
@router.patch("/select-best")
async def select_best_version(
    body: SelectBestRequest,
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    application_id = _validate_uuid(body.application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)
    best_resume = await _get_resume_or_404(db, body.best_resume_id)

    if best_resume.application_id != application_id:
        raise ApplicationMismatchError(
            "best_resume_id does not belong to the given application_id."
        )

    await db.execute(
        update(Resume)
        .where(Resume.application_id == application_id)
        .values(is_best_version=False)
    )
    best_resume.is_best_version = True
    db.add(best_resume)
    await db.commit()

    result = await db.execute(
        select(Resume.id).where(Resume.application_id == application_id)
    )
    updated_count = len(result.scalars().all())

    payload = SelectBestResponse(
        application_id=application_id,
        best_resume_id=best_resume.id,
        version_number=best_resume.version_number,
        updated_versions=updated_count,
    )
    return success_response(payload.model_dump(mode="json"))
