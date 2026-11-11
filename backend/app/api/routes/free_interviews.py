"""One text-only, three-question interview for each FREE account."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.resume_session import get_db as get_resume_db
from app.models.application import Application
from app.models.interview import Interview, InterviewAnswer, InterviewAnswerEvaluation, InterviewQuestion
from app.models.resume import Resume
from app.models.user import Plan, User
from app.schemas.interview import (
    APIResponse,
    AnswerSubmitRequest,
    InterviewAnswerData,
    InterviewAnswerEvaluationData,
    InterviewData,
    InterviewFullSessionData,
    InterviewQuestionData,
    InterviewQuestionWithAnswerData,
    InterviewQuestionsData,
    GeneratedQuestion,
)
from app.services.entitlements import lock_user
from app.services.interview_evaluation import evaluate_answer_for_application
from app.services.interview_questions import build_adaptation_context, generate_question_for_application

router = APIRouter(prefix="/interviews/free-trial", tags=["free text interview"])


class FreeTrialRequest(BaseModel):
    role: str = Field(default="Software Engineer", min_length=2, max_length=120)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Enter a role to tailor your interview")
        return value


def _interview_data(interview: Interview) -> InterviewData:
    return InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=len(interview.questions),
        question_target=interview.question_target,
        mode="text",
        started_at=interview.started_at,
    )


def _question_data(question: InterviewQuestion) -> InterviewQuestionData:
    return InterviewQuestionData(
        question_id=question.id,
        interview_id=question.interview_id,
        question_number=question.question_number,
        question=question.question,
        topic=question.topic,
        question_type=question.question_type,
        difficulty=question.difficulty,
        expected_skills=question.expected_skills,
        reason=question.reason,
    )


def _answer_data(answer: InterviewAnswer) -> InterviewAnswerData:
    return InterviewAnswerData(
        answer_id=answer.id,
        interview_id=answer.interview_id,
        question_id=answer.question_id,
        answer_text=answer.answer_text,
        source="typed",
        duration_seconds=answer.duration_seconds,
        submitted_at=answer.created_at,
    )


def _evaluation_data(evaluation: InterviewAnswerEvaluation) -> InterviewAnswerEvaluationData:
    return InterviewAnswerEvaluationData(
        evaluation_id=evaluation.id,
        answer_id=evaluation.answer_id,
        overall_score=evaluation.overall_score,
        relevance_score=evaluation.relevance_score,
        correctness_score=evaluation.correctness_score,
        depth_score=evaluation.depth_score,
        clarity_score=evaluation.clarity_score,
        evidence_score=evaluation.evidence_score,
        confidence_score=evaluation.confidence_score,
        confidence_rationale=evaluation.confidence_rationale,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        missing_points=evaluation.missing_points,
        feedback=evaluation.feedback,
        evaluated_at=evaluation.evaluated_at,
        technical_correctness=evaluation.correctness_score,
        relevance=evaluation.relevance_score,
        reasoning=evaluation.depth_score,
        communication=evaluation.clarity_score,
    )


def _owned_trial(interview_id: UUID, current_user: User, db: DbSession) -> tuple[Interview, Application]:
    row = db.execute(
        select(Interview, Application)
        .join(Application, Interview.application_id == Application.id)
        .where(
            Interview.id == interview_id,
            Interview.is_trial.is_(True),
            Application.user_id == current_user.id,
            Application.is_scratch.is_(True),
        )
    ).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Free interview not found")
    return row


@router.get("/status")
async def get_free_interview_status(
    current_user: CurrentUser,
    db: DbSession,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    application = db.scalar(
        select(Application).where(Application.user_id == current_user.id, Application.is_scratch.is_(True))
    )
    has_resume = False
    if application:
        has_resume = bool(
            (await resume_db.execute(
                select(Resume.id).where(Resume.application_id == str(application.id)).limit(1)
            )).scalar_one_or_none()
        )
    settings = get_settings()
    trial = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .where(
            Interview.is_trial.is_(True),
            Application.user_id == current_user.id,
            Application.is_scratch.is_(True),
        )
        .order_by(Interview.created_at.desc())
    )
    return {
        "available": current_user.plan == Plan.FREE and not current_user.trial_used and has_resume,
        "trial_used": current_user.trial_used,
        "session_id": str(trial.id) if trial and trial.status != "completed" else None,
        "completed": bool(trial and trial.status == "completed"),
        "resume_available": has_resume,
        "question_limit": min(3, settings.free_trial_question_limit),
    }


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_free_interview(
    payload: FreeTrialRequest,
    db: DbSession,
    current_user: CurrentUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    user = lock_user(db, current_user.id)
    if user.plan != Plan.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Free interview is for FREE accounts")
    if user.trial_used:
        existing = db.scalar(
            select(Interview)
            .join(Application, Interview.application_id == Application.id)
            .where(
                Interview.is_trial.is_(True),
                Application.user_id == user.id,
                Application.is_scratch.is_(True),
                Interview.status != "completed",
            )
            .order_by(Interview.created_at.desc())
        )
        if existing:
            return APIResponse(success=True, data=_interview_data(existing), error=None)
        raise HTTPException(status.HTTP_409_CONFLICT, "Your free three-question interview has already been used")

    application = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.is_scratch.is_(True))
    )
    if application is None:
        application = Application(
            user_id=user.id,
            company="Quick Scan",
            role=payload.role,
            is_scratch=True,
        )
        db.add(application)
        db.flush()
    else:
        application.role = payload.role

    has_resume = (await resume_db.execute(
        select(Resume.id).where(Resume.application_id == str(application.id)).limit(1)
    )).scalar_one_or_none()
    if not has_resume:
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload a resume from the ATS checker before starting your free interview")

    interview = Interview(
        application_id=application.id,
        personality="mixed",
        difficulty="medium",
        is_trial=True,
        question_target=min(3, get_settings().free_trial_question_limit),
        mode="text",
        status="created",
    )
    user.trial_used = True
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return APIResponse(success=True, data=_interview_data(interview), error=None)


@router.get("/{interview_id}", response_model=APIResponse)
def get_free_interview(interview_id: UUID, db: DbSession, current_user: CurrentUser):
    interview, _application = _owned_trial(interview_id, current_user, db)
    interview = db.scalar(
        select(Interview)
        .where(Interview.id == interview.id)
        .options(
            selectinload(Interview.questions)
            .selectinload(InterviewQuestion.answers)
            .selectinload(InterviewAnswer.evaluation)
        )
    )
    items = []
    scores = []
    confidences = []
    for question in interview.questions:
        answer = question.answers[0] if question.answers else None
        evaluation = answer.evaluation if answer else None
        if evaluation:
            scores.append(evaluation.overall_score)
            confidences.append(evaluation.confidence_score)
        items.append(
            InterviewQuestionWithAnswerData(
                question=_question_data(question),
                answer=_answer_data(answer) if answer else None,
                evaluation=_evaluation_data(evaluation) if evaluation else None,
            )
        )
    data = InterviewFullSessionData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_target=interview.question_target,
        started_at=interview.started_at,
        completed_at=interview.completed_at,
        created_at=interview.created_at,
        summary=interview.summary,
        recommendation=interview.recommendation,
        average_score=sum(scores) / len(scores) if scores else None,
        average_confidence=sum(confidences) / len(confidences) if confidences else None,
        mode="text",
        visual_analysis=None,
        items=items,
    )
    return APIResponse(success=True, data=data, error=None)


@router.post("/{interview_id}/questions", response_model=APIResponse)
async def generate_free_question(
    interview_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    interview, application = _owned_trial(interview_id, current_user, db)
    if interview.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This free interview is complete")
    number = (db.scalar(select(func.max(InterviewQuestion.question_number)).where(
        InterviewQuestion.interview_id == interview.id
    )) or 0) + 1
    if number > interview.question_target:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your free interview is limited to three questions")
    previous = db.scalars(
        select(InterviewQuestion.question)
        .where(InterviewQuestion.interview_id == interview.id)
        .order_by(InterviewQuestion.question_number)
    ).all()
    adaptation = build_adaptation_context(interview.id, number, db)
    generated: GeneratedQuestion = await generate_question_for_application(
        application=application,
        personality=interview.personality,
        difficulty=interview.difficulty,
        question_number=number,
        previous_questions=list(previous),
        resume_db=resume_db,
        adaptation=adaptation,
    )
    question = InterviewQuestion(
        interview_id=interview.id,
        question_number=number,
        question=generated.question,
        topic=generated.topic,
        question_type=generated.question_type,
        difficulty=generated.difficulty.value,
        expected_skills=generated.expected_skills,
        reason=generated.reason,
    )
    db.add(question)
    if interview.status == "created":
        interview.status = "in_progress"
        interview.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(question)
    return APIResponse(success=True, data=_question_data(question), error=None)


@router.post("/{interview_id}/answers", response_model=APIResponse)
def submit_free_answer(
    interview_id: UUID,
    payload: AnswerSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    interview, _application = _owned_trial(interview_id, current_user, db)
    if interview.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This free interview is complete")
    if payload.source.value != "typed":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The free interview supports text answers only")
    question = db.scalar(select(InterviewQuestion).where(
        InterviewQuestion.id == payload.question_id,
        InterviewQuestion.interview_id == interview.id,
    ))
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    answer = db.scalar(select(InterviewAnswer).where(
        InterviewAnswer.interview_id == interview.id,
        InterviewAnswer.question_id == question.id,
    ).options(selectinload(InterviewAnswer.evaluation)))
    if answer is None:
        answer = InterviewAnswer(interview_id=interview.id, question_id=question.id)
        db.add(answer)
    else:
        answer.evaluation = None
    answer.answer_text = payload.answer_text
    answer.source = "typed"
    answer.duration_seconds = payload.duration_seconds
    answer.audio_storage_key = None
    answer.audio_mime_type = None
    answer.audio_size_bytes = None
    db.commit()
    db.refresh(answer)
    return APIResponse(success=True, data=_answer_data(answer), error=None)


@router.post("/{interview_id}/answers/{answer_id}/evaluate", response_model=APIResponse)
async def evaluate_free_answer(
    interview_id: UUID,
    answer_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    interview, application = _owned_trial(interview_id, current_user, db)
    if interview.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This free interview is complete")
    answer = db.scalar(select(InterviewAnswer).where(
        InterviewAnswer.id == answer_id,
        InterviewAnswer.interview_id == interview.id,
    ).options(selectinload(InterviewAnswer.evaluation)))
    if not answer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")
    question = db.scalar(select(InterviewQuestion).where(
        InterviewQuestion.id == answer.question_id,
        InterviewQuestion.interview_id == interview.id,
    ))
    generated = await evaluate_answer_for_application(
        application=application,
        interview=interview,
        question=question,
        answer=answer,
        resume_db=resume_db,
    )
    evaluation = db.scalar(select(InterviewAnswerEvaluation).where(
        InterviewAnswerEvaluation.answer_id == answer.id
    ))
    is_new_evaluation = evaluation is None
    if evaluation is None:
        evaluation = InterviewAnswerEvaluation(answer_id=answer.id)
        db.add(evaluation)
    evaluation.overall_score = generated.overall_score
    evaluation.relevance_score = generated.relevance_score
    evaluation.correctness_score = generated.correctness_score
    evaluation.depth_score = generated.depth_score
    evaluation.clarity_score = generated.clarity_score
    evaluation.evidence_score = generated.evidence_score
    evaluation.confidence_score = generated.confidence_score
    evaluation.confidence_rationale = generated.confidence_rationale
    evaluation.strengths = generated.strengths
    evaluation.weaknesses = generated.weaknesses
    evaluation.missing_points = generated.missing_points
    evaluation.feedback = generated.feedback

    evaluated_count = db.scalar(
        select(func.count(InterviewAnswerEvaluation.id))
        .join(InterviewAnswer, InterviewAnswerEvaluation.answer_id == InterviewAnswer.id)
        .where(InterviewAnswer.interview_id == interview.id)
    ) or 0
    if is_new_evaluation:
        evaluated_count += 1
    if question.question_number == interview.question_target and evaluated_count >= interview.question_target:
        interview.status = "completed"
        interview.completed_at = datetime.now(timezone.utc)
        interview.summary = "You completed your free three-question text interview. Upgrade to continue practicing with Premium."
    db.commit()
    db.refresh(evaluation)
    return APIResponse(success=True, data=_evaluation_data(evaluation), error=None)
