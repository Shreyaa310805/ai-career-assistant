"""Application-context loading for persisted interview answer evaluations."""
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.interview import Interview, InterviewAnswer, InterviewQuestion
from app.models.resume import AtsReport, Resume
from app.schemas.interview import GeneratedAnswerEvaluation
from app.services.resumes.gemini_service import get_gemini_service


async def evaluate_answer_for_application(
    *, application: Application, interview: Interview, question: InterviewQuestion,
    answer: InterviewAnswer, resume_db: AsyncSession,
) -> GeneratedAnswerEvaluation:
    """Load bounded resume/ATS context without making it a hard dependency."""
    resume_evidence = ""
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    try:
        result = await resume_db.execute(
            select(Resume).where(Resume.application_id == str(application.id)).order_by(
                Resume.is_best_version.desc(), Resume.created_at.desc()
            )
        )
        resume = result.scalars().first()
        if resume:
            resume_evidence = resume.raw_text[:8000]
            reports = await resume_db.execute(
                select(AtsReport).where(AtsReport.resume_id == resume.id).order_by(AtsReport.created_at.desc())
            )
            report = reports.scalars().first()
            if report:
                matched_skills = list(report.matched_skills)
                missing_skills = list(report.missing_skills)
    except SQLAlchemyError:
        pass

    context_skills = list(dict.fromkeys([*question.expected_skills, *matched_skills, *missing_skills]))
    return get_gemini_service().evaluate_interview_answer(
        question=question.question, question_type=question.question_type, topic=question.topic,
        difficulty=question.difficulty, expected_skills=context_skills, personality=interview.personality,
        job_description=application.job_description or "", resume_evidence=resume_evidence,
        answer_text=answer.answer_text,
    )
