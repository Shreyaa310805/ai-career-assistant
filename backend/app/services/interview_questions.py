"""Application-context loading and AI generation for interview questions."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.resume import AtsReport, Resume
from app.schemas.interview import DifficultyEnum, GeneratedQuestion
from app.services.resumes.gemini_service import get_gemini_service


async def generate_question_for_application(
    *, application: Application, personality: str, difficulty: str,
    question_number: int, previous_questions: list[str], resume_db: AsyncSession,
) -> GeneratedQuestion:
    """Build a privacy-safe context from the latest best resume/ATS report."""
    resume_skills: list[str] = []
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    resume_evidence = ""
    try:
        result = await resume_db.execute(
            select(Resume).where(Resume.application_id == str(application.id)).order_by(
                Resume.is_best_version.desc(), Resume.created_at.desc()
            )
        )
        resume = result.scalars().first()
        if resume:
            resume_skills = list(resume.parsed_data.get("skills", []))
            # Raw resume text contains project descriptions that the parsed
            # schema does not yet model. Bound it before handing it to the AI.
            resume_evidence = resume.raw_text[:12000]
            reports = await resume_db.execute(
                select(AtsReport).where(AtsReport.resume_id == resume.id).order_by(AtsReport.created_at.desc())
            )
            report = reports.scalars().first()
            if report:
                matched_skills = list(report.matched_skills)
                missing_skills = list(report.missing_skills)
    except SQLAlchemyError:
        # A question can still be generated from the stored application/JD if
        # the optional resume store is not yet initialized.
        pass

    return get_gemini_service().generate_interview_question(
        role=application.role,
        job_description=application.job_description or "",
        personality=personality,
        difficulty=DifficultyEnum(difficulty),
        resume_skills=resume_skills,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        question_number=question_number,
        previous_questions=previous_questions,
        resume_evidence=resume_evidence,
    )
