"""
Module 1 (Resume & ATS) route handlers — the five endpoints of the
frozen API contract:

    POST  /api/v1/resumes/upload
    POST  /api/v1/resumes/analyze
    GET   /api/v1/resumes/versions/{application_id}
    POST  /api/v1/resumes/compare
    PATCH /api/v1/resumes/select-best

Every handler returns via success_response() (the {success,data,error}
envelope); every failure raises an ApiError subclass that the global
exception handler in app/main.py converts to the same envelope.

Two additive endpoints sit alongside the frozen five and change none of them:

    GET   /api/v1/resumes/library
    POST  /api/v1/resumes/reuse
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.application import Application

from app.db.resume_session import get_db
from app.services.resumes.exceptions import ApplicationMismatchError, ResumeNotFoundError
from app.models.resume import AtsReport, Resume
from app.services.resumes.response import success_response
from app.schemas.resume import (
    CompareRequest,
    CompareResumesResponse,
    LatestAtsSummary,
    ParsedResumeData,
    ResumeLibraryItem,
    ResumeLibraryResponse,
    ResumeVersionSummary,
    ReuseResumeRequest,
    SelectBestRequest,
    SelectBestResponse,
    UploadResumeResponse,
    VersionListResponse,
)
from app.services.resumes.pipeline import (
    get_resume_or_404,
    ingest_resume,
    public_file_reference,
    public_resume_details,
    resolve_jd_content,
    run_analysis,
    validate_uuid,
)
from app.services.resumes.versioning import (
    diff_versions,
    get_latest_ats_report,
    next_version_number,
    recommend_version,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _require_owned_application(application_id: str, current_user: CurrentUser, db: DbSession) -> None:
    """Bind resume records to an application owned by the current user."""
    application = db.get(Application, uuid.UUID(application_id))
    if application is None:
        # Keep the response deliberately non-specific, matching application routes.
        raise ResumeNotFoundError("No application found for this resume operation.")
    if application.user_id != current_user.id:
        raise ResumeNotFoundError("No application found for this resume operation.")


def _resume_to_summary(resume: Resume, latest_report: AtsReport | None) -> ResumeVersionSummary:
    return ResumeVersionSummary(
        resume_id=resume.id,
        application_id=resume.application_id,
        version_number=resume.version_number,
        file_url=public_file_reference(resume.id),
        is_best_version=resume.is_best_version,
        created_at=resume.created_at,
        parsed_data=public_resume_details(ParsedResumeData.model_validate(resume.parsed_data)),
        latest_ats_report=(
            LatestAtsSummary(
                report_id=latest_report.id,
                ats_score=latest_report.ats_score,
                match_score=latest_report.match_score,
                created_at=latest_report.created_at,
                ats_breakdown=(latest_report.score_breakdown or {}).get("ats"),
                match_breakdown=(latest_report.score_breakdown or {}).get("match"),
                ats_explanations=(latest_report.score_breakdown or {}).get("ats_explanations"),
                ats_summary=(latest_report.score_breakdown or {}).get("ats_summary"),
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
    application_id = validate_uuid(application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)

    _resume, payload = await ingest_resume(
        file_bytes=await file.read(),
        filename=file.filename or "",
        content_type=file.content_type,
        application_id=application_id,
        db=db,
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
    application_id = validate_uuid(application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)
    resume = await get_resume_or_404(db, resume_id)

    if resume.application_id != application_id:
        raise ApplicationMismatchError(
            "resume_id does not belong to the given application_id."
        )

    jd_content = await resolve_jd_content(jd_file, jd_text)

    _report, payload = await run_analysis(
        resume=resume,
        application_id=application_id,
        jd_content=jd_content,
        db=db,
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
    application_id = validate_uuid(application_id, "application_id")
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
    resume_v1 = await get_resume_or_404(db, body.resume_id_v1)
    resume_v2 = await get_resume_or_404(db, body.resume_id_v2)

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
    application_id = validate_uuid(body.application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)
    best_resume = await get_resume_or_404(db, body.best_resume_id)

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


# --------------------------------------------------------------------------
# Additive: resume library + reuse. Not part of the frozen contract above.
# --------------------------------------------------------------------------
@router.get("/library")
async def resume_library(
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    """Every resume the caller has uploaded, across applications and quick scans."""
    applications = {
        str(app.id): app
        for app in application_db.scalars(
            select(Application).where(Application.user_id == current_user.id)
        )
    }
    if not applications:
        return success_response(ResumeLibraryResponse(resumes=[]).model_dump(mode="json"))

    result = await db.execute(
        select(Resume)
        .where(Resume.application_id.in_(list(applications)))
        .order_by(Resume.created_at.desc())
    )
    items = []
    for resume in result.scalars().all():
        app = applications[resume.application_id]
        parsed = ParsedResumeData.model_validate(resume.parsed_data)
        items.append(
            ResumeLibraryItem(
                resume_id=resume.id,
                application_id=resume.application_id,
                company=app.company,
                role=app.role,
                label="Quick scan" if app.is_scratch else f"{app.company} — {app.role}",
                is_quick_scan=app.is_scratch,
                version_number=resume.version_number,
                created_at=resume.created_at,
                skills=parsed.skills,
                experience_years=parsed.experience_years,
            )
        )
    return success_response(ResumeLibraryResponse(resumes=items).model_dump(mode="json"))


@router.post("/reuse")
async def reuse_resume(
    body: ReuseResumeRequest,
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    """Copy an existing resume's parsed data and text into another application.

    The stored file is referenced, not re-uploaded. The copy takes the next
    version number of the *target* application (1 for a fresh one) rather than
    inheriting the source's, and carries no ATS reports: it has not been scored
    against the target's job description.
    """
    application_id = validate_uuid(body.application_id, "application_id")
    _require_owned_application(application_id, current_user, application_db)

    source = await get_resume_or_404(db, body.source_resume_id)
    # The source must also be one of the caller's own resumes.
    _require_owned_application(source.application_id, current_user, application_db)

    version_number = await next_version_number(db, application_id)
    clone = Resume(
        id=str(uuid.uuid4()),
        application_id=application_id,
        version_number=version_number,
        file_url=source.file_url,
        raw_text=source.raw_text,
        parsed_data=dict(source.parsed_data),
        is_best_version=(version_number == 1),
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)

    payload = UploadResumeResponse(
        resume_id=clone.id,
        application_id=clone.application_id,
        version_number=clone.version_number,
        parsed_data=public_resume_details(ParsedResumeData.model_validate(clone.parsed_data)),
    )
    return success_response(payload.model_dump(mode="json"))
