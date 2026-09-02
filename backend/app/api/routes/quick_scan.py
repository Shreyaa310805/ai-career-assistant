"""FREE-tier resume scanning.

Every `/resumes/*` endpoint is scoped to an application the caller owns, and
that contract is frozen. FREE accounts do not get the application tracker, so
this router gives them the same ATS pipeline against a single server-managed
"scratch" application that is created on demand and never surfaced in the
application list.

Nothing here reimplements scoring or storage: it resolves the scratch
application, then calls the same `app.services.resumes.pipeline` functions the
frozen routes use. Responses use the identical {success, data, error} envelope.
"""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.db.resume_session import get_db
from app.models.application import Application
from app.models.resume import AtsReport, Resume
from app.models.user import User
from app.schemas.resume import ParsedResumeData
from app.services.resumes.exceptions import ApplicationMismatchError
from app.services.resumes.pipeline import (
    get_resume_or_404,
    ingest_resume,
    public_resume_details,
    resolve_jd_content,
    run_analysis,
)
from app.services.resumes.response import success_response

router = APIRouter(prefix="/quick-scan", tags=["quick scan"])

SCRATCH_LABEL = "Quick Scan"


def get_or_create_scratch_application(user: User, db: Session) -> Application:
    """One hidden application per user, reused across every quick scan."""
    application = db.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.is_scratch.is_(True),
        )
    )
    if application is not None:
        return application

    application = Application(
        user_id=user.id,
        company=SCRATCH_LABEL,
        role=SCRATCH_LABEL,
        is_scratch=True,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def _scratch_id(current_user: CurrentUser, application_db: DbSession) -> str:
    return str(get_or_create_scratch_application(current_user, application_db).id)


@router.post("/resume")
async def quick_scan_upload(
    current_user: CurrentUser,
    application_db: DbSession,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a resume without needing an application. FREE and PREMIUM."""
    _resume, payload = await ingest_resume(
        file_bytes=await file.read(),
        filename=file.filename or "",
        content_type=file.content_type,
        application_id=_scratch_id(current_user, application_db),
        db=db,
    )
    return success_response(payload.model_dump(mode="json"))


@router.post("/analyze")
async def quick_scan_analyze(
    current_user: CurrentUser,
    application_db: DbSession,
    resume_id: str = Form(...),
    jd_file: UploadFile | None = File(None),
    jd_text: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Score an uploaded resume against a job description. FREE and PREMIUM."""
    application_id = _scratch_id(current_user, application_db)
    resume = await get_resume_or_404(db, resume_id)
    if resume.application_id != application_id:
        # The resume belongs to someone else, or to a tracked application.
        raise ApplicationMismatchError("resume_id does not belong to this quick scan.")

    jd_content = await resolve_jd_content(jd_file, jd_text)
    _report, payload = await run_analysis(
        resume=resume,
        application_id=application_id,
        jd_content=jd_content,
        db=db,
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/latest")
async def quick_scan_latest(
    current_user: CurrentUser,
    application_db: DbSession,
    db: AsyncSession = Depends(get_db),
):
    """The caller's most recent quick scan, so the dashboard survives a reload."""
    application = get_or_create_scratch_application(current_user, application_db)

    resume = (
        await db.execute(
            select(Resume)
            .where(Resume.application_id == str(application.id))
            .order_by(Resume.created_at.desc())
        )
    ).scalars().first()

    if resume is None:
        return success_response({"resume": None, "report": None})

    report = (
        await db.execute(
            select(AtsReport)
            .where(AtsReport.resume_id == resume.id)
            .order_by(AtsReport.created_at.desc())
        )
    ).scalars().first()

    parsed = ParsedResumeData.model_validate(resume.parsed_data)
    return success_response(
        {
            "resume": {
                "resume_id": resume.id,
                "version_number": resume.version_number,
                "created_at": resume.created_at.isoformat(),
                "parsed_data": public_resume_details(parsed).model_dump(mode="json"),
            },
            "report": None
            if report is None
            else {
                "report_id": report.id,
                "ats_score": report.ats_score,
                "match_score": report.match_score,
                "matched_skills": report.matched_skills,
                "missing_skills": report.missing_skills,
                "improvement_suggestions": report.improvement_suggestions,
                "ats_breakdown": (report.score_breakdown or {}).get("ats"),
                "match_breakdown": (report.score_breakdown or {}).get("match"),
                "created_at": report.created_at.isoformat(),
            },
        }
    )
