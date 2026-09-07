from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, PremiumUser
from app.models.application import Application
from app.db.resume_session import get_db as get_resume_db
from app.models.interview import Interview, InterviewQuestion
from app.schemas.interview import (
    APIResponse, GenerateQuestionRequest, GeneratedQuestion, InterviewCreateRequest,
    InterviewData, InterviewQuestionData, InterviewQuestionsData,
)
from app.services.interview_questions import generate_question_for_application

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _interview_data(interview: Interview) -> InterviewData:
    return InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=len(interview.questions),
        started_at=interview.started_at,
    )


def _question_data(question: InterviewQuestion) -> InterviewQuestionData:
    return InterviewQuestionData(
        question_id=question.id, interview_id=question.interview_id,
        question_number=question.question_number, question=question.question,
        topic=question.topic, question_type=question.question_type,
        difficulty=question.difficulty, expected_skills=question.expected_skills,
        reason=question.reason,
    )


def _owned_application(application_id: UUID, user_id: UUID, db: DbSession) -> Application:
    application = db.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user_id,
            Application.is_scratch.is_(False),
        )
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.post("", response_model=APIResponse)
def create_interview(payload: InterviewCreateRequest, db: DbSession, current_user: PremiumUser):
    _owned_application(payload.application_id, current_user.id, db)
    interview = Interview(
        application_id=payload.application_id,
        personality=payload.personality.value,
        difficulty=payload.difficulty.value,
        status="created",
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return APIResponse(success=True, data=_interview_data(interview), error=None)


@router.get("/{interview_id}", response_model=APIResponse)
def get_interview(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .where(
            Interview.id == interview_id,
            Application.user_id == current_user.id,
            Application.is_scratch.is_(False),
        )
    )
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return APIResponse(success=True, data=_interview_data(interview), error=None)


def _owned_interview(interview_id: UUID, user_id: UUID, db: DbSession) -> Interview:
    interview = db.scalar(
        select(Interview).join(Application, Interview.application_id == Application.id).where(
            Interview.id == interview_id, Application.user_id == user_id, Application.is_scratch.is_(False)
        )
    )
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview


@router.post("/{interview_id}/questions", response_model=APIResponse)
async def generate_question(
    interview_id: UUID, payload: GenerateQuestionRequest, db: DbSession, current_user: PremiumUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    interview = _owned_interview(interview_id, current_user.id, db)
    application = _owned_application(interview.application_id, current_user.id, db)
    question_number = (db.scalar(select(func.max(InterviewQuestion.question_number)).where(
        InterviewQuestion.interview_id == interview.id
    )) or 0) + 1
    current_interview_questions = db.scalars(select(InterviewQuestion.question).where(
        InterviewQuestion.interview_id == interview.id
    ).order_by(InterviewQuestion.question_number)).all()
    application_questions = db.scalars(select(InterviewQuestion.question).join(Interview).where(
        Interview.application_id == interview.application_id
    ).order_by(InterviewQuestion.created_at)).all()
    # Retain the current interview's ordered history while supplementing it
    # with prior sessions for this application only.
    previous_questions = list(dict.fromkeys([*current_interview_questions, *application_questions]))
    generated: GeneratedQuestion = await generate_question_for_application(
        application=application, personality=interview.personality, difficulty=interview.difficulty,
        question_number=question_number, previous_questions=previous_questions, resume_db=resume_db,
    )
    question = InterviewQuestion(
        interview_id=interview.id, question_number=question_number, question=generated.question,
        topic=generated.topic, question_type=generated.question_type,
        difficulty=generated.difficulty.value, expected_skills=generated.expected_skills, reason=generated.reason,
    )
    db.add(question)
    try:
        db.commit()
    except IntegrityError:
        # The unique DB constraint is the final guard for simultaneous Next
        # Question requests. Do not create duplicate positions; the client can
        # retry and receive the newly available next number.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A question is already being generated; retry shortly")
    db.refresh(question)
    return APIResponse(success=True, data=_question_data(question), error=None)


@router.get("/{interview_id}/questions", response_model=APIResponse)
def list_questions(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = _owned_interview(interview_id, current_user.id, db)
    questions = db.scalars(select(InterviewQuestion).where(
        InterviewQuestion.interview_id == interview.id
    ).order_by(InterviewQuestion.question_number)).all()
    return APIResponse(success=True, data=InterviewQuestionsData(
        interview_id=interview.id, questions=[_question_data(question) for question in questions]
    ), error=None)
