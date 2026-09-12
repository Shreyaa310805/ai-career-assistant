from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, PremiumUser
from app.models.application import Application
from app.db.resume_session import get_db as get_resume_db
from app.models.interview import Interview, InterviewAnswer, InterviewAnswerEvaluation, InterviewQuestion
from app.schemas.interview import (
    APIResponse, AnswerSubmitRequest, CompleteInterviewData, GeneratedAnswerEvaluation, GeneratedQuestion,
    InterviewAnswerData, InterviewAnswerEvaluationData, InterviewCreateRequest, InterviewData,
    InterviewFullSessionData, InterviewHistoryData, InterviewQuestionData, InterviewQuestionsData,
    InterviewQuestionWithAnswerData, InterviewSummaryData,
)
from app.services.interview_evaluation import evaluate_answer_for_application, summarize_interview_for_application
from app.services.interview_questions import build_adaptation_context, generate_question_for_application

from app.services.interview_audio import read_audio, transcribe_audio, save_audio, remove_audio

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _interview_data(interview: Interview) -> InterviewData:
    return InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=len(interview.questions),
        question_target=interview.question_target,
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


def _answer_data(answer: InterviewAnswer) -> InterviewAnswerData:
    return InterviewAnswerData(
        answer_id=answer.id, interview_id=answer.interview_id, question_id=answer.question_id,
        answer_text=answer.answer_text, source=answer.source, duration_seconds=answer.duration_seconds,
        submitted_at=answer.created_at, audio_mime_type=answer.audio_mime_type,
        audio_size_bytes=answer.audio_size_bytes,
    )


def _evaluation_data(evaluation: InterviewAnswerEvaluation) -> InterviewAnswerEvaluationData:
    return InterviewAnswerEvaluationData(
        evaluation_id=evaluation.id, answer_id=evaluation.answer_id, overall_score=evaluation.overall_score,
        relevance_score=evaluation.relevance_score, correctness_score=evaluation.correctness_score,
        depth_score=evaluation.depth_score, clarity_score=evaluation.clarity_score, evidence_score=evaluation.evidence_score,
        confidence_score=evaluation.confidence_score, confidence_rationale=evaluation.confidence_rationale,
        strengths=evaluation.strengths, weaknesses=evaluation.weaknesses, missing_points=evaluation.missing_points,
        feedback=evaluation.feedback, evaluated_at=evaluation.evaluated_at,
        technical_correctness=evaluation.correctness_score, relevance=evaluation.relevance_score,
        reasoning=evaluation.depth_score, communication=evaluation.clarity_score,
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
        question_target=payload.question_target,
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


def _answer_for_interview(answer_id: UUID, interview_id: UUID, db: DbSession) -> InterviewAnswer:
    answer = db.scalar(select(InterviewAnswer).where(
        InterviewAnswer.id == answer_id, InterviewAnswer.interview_id == interview_id
    ))
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    return answer


@router.post("/{interview_id}/questions", response_model=APIResponse)
async def generate_question(
    interview_id: UUID, db: DbSession, current_user: PremiumUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    interview = _owned_interview(interview_id, current_user.id, db)
    application = _owned_application(interview.application_id, current_user.id, db)
    if interview.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This interview session is already completed")
    question_number = (db.scalar(select(func.max(InterviewQuestion.question_number)).where(
        InterviewQuestion.interview_id == interview.id
    )) or 0) + 1
    if question_number > interview.question_target:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This session is limited to {interview.question_target} questions",
        )
    current_interview_questions = db.scalars(select(InterviewQuestion.question).where(
        InterviewQuestion.interview_id == interview.id
    ).order_by(InterviewQuestion.question_number)).all()
    application_questions = db.scalars(select(InterviewQuestion.question).join(Interview).where(
        Interview.application_id == interview.application_id
    ).order_by(InterviewQuestion.created_at)).all()
    # Retain the current interview's ordered history while supplementing it
    # with prior sessions for this application only.
    previous_questions = list(dict.fromkeys([*current_interview_questions, *application_questions]))
    # Adaptive: from question 3 onward, factor in this session's own running
    # performance to steer difficulty/topic. Questions 1-2 use the fixed
    # baseline personality/difficulty chosen at setup.
    adaptation = build_adaptation_context(interview.id, question_number, db)
    generated: GeneratedQuestion = await generate_question_for_application(
        application=application, personality=interview.personality, difficulty=interview.difficulty,
        question_number=question_number, previous_questions=previous_questions, resume_db=resume_db,
        adaptation=adaptation,
    )
    question = InterviewQuestion(
        interview_id=interview.id, question_number=question_number, question=generated.question,
        topic=generated.topic, question_type=generated.question_type,
        difficulty=generated.difficulty.value, expected_skills=generated.expected_skills, reason=generated.reason,
    )
    db.add(question)
    if interview.status == "created":
        interview.status = "in_progress"
        interview.started_at = datetime.now(timezone.utc)
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


def _save_answer_row(interview_id, question_id, text, source, duration, db,
                     audio_key=None, audio_mime=None, audio_size=None):
    """Shared text/audio persistence. Caller holds the question row lock."""
    answer = db.scalar(select(InterviewAnswer).where(
        InterviewAnswer.interview_id == interview_id, InterviewAnswer.question_id == question_id,
    ).options(selectinload(InterviewAnswer.evaluation)))
    old_key = None
    if answer is None:
        answer = InterviewAnswer(interview_id=interview_id, question_id=question_id)
        db.add(answer)
    else:
        old_key = answer.audio_storage_key
        answer.evaluation = None
    answer.answer_text = text
    answer.source = source
    answer.duration_seconds = duration
    answer.audio_storage_key = audio_key
    answer.audio_mime_type = audio_mime
    answer.audio_size_bytes = audio_size
    return answer, old_key


@router.post("/{interview_id}/answers", response_model=APIResponse)
def submit_answer(
    interview_id: UUID, payload: AnswerSubmitRequest, db: DbSession, current_user: PremiumUser,
):
    _owned_interview(interview_id, current_user.id, db)
    question = db.scalar(select(InterviewQuestion).where(
        InterviewQuestion.id == payload.question_id, InterviewQuestion.interview_id == interview_id
    ).with_for_update())
    if not question:
        # Do not disclose whether a question exists in another session.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    answer, old_audio_key = _save_answer_row(
        interview_id, question.id, payload.answer_text, payload.source.value,
        payload.duration_seconds, db,
    )
    db.commit()
    db.refresh(answer)
    remove_audio(old_audio_key)
    return APIResponse(success=True, data=_answer_data(answer), error=None)


@router.post("/{interview_id}/questions/{question_id}/audio-answer", response_model=APIResponse)
async def submit_audio_answer(
    interview_id: UUID, question_id: UUID, db: DbSession, current_user: PremiumUser,
    audio: UploadFile = File(...),
    duration_seconds: float | None = Form(default=None, ge=0, le=600),
):
    interview = _owned_interview(interview_id, current_user.id, db)
    if interview.status == "completed":
        raise HTTPException(409, "This interview session is already completed")
    question = db.scalar(select(InterviewQuestion).where(
        InterviewQuestion.id == question_id, InterviewQuestion.interview_id == interview_id,
    ))
    if question is None:
        raise HTTPException(404, "Question not found")
    try:
        data, mime = await read_audio(audio)
    finally:
        await audio.close()
    # Do not hold a database transaction while waiting on the provider.
    db.rollback()
    transcript = await transcribe_audio(data, mime)
    key = await save_audio(data, mime, interview_id)
    old_key = None
    try:
        interview = _owned_interview(interview_id, current_user.id, db)
        if interview.status == "completed":
            raise HTTPException(409, "This interview session is already completed")
        question = db.scalar(select(InterviewQuestion).where(
            InterviewQuestion.id == question_id, InterviewQuestion.interview_id == interview_id,
        ).with_for_update())
        if question is None:
            raise HTTPException(404, "Question not found")
        answer, old_key = _save_answer_row(
            interview_id, question_id, transcript, "voice", duration_seconds, db,
            audio_key=key, audio_mime=mime, audio_size=len(data),
        )
        db.commit()
    except Exception:
        db.rollback()
        remove_audio(key)
        raise
    remove_audio(old_key)
    db.refresh(answer)
    # Same two-step contract as typed answers: the UI calls the existing evaluator.
    return APIResponse(success=True, data=_answer_data(answer), error=None)


@router.post("/{interview_id}/answers/{answer_id}/evaluate", response_model=APIResponse)
async def evaluate_answer(
    interview_id: UUID, answer_id: UUID, db: DbSession, current_user: PremiumUser,
    resume_db: AsyncSession = Depends(get_resume_db),
):
    interview = _owned_interview(interview_id, current_user.id, db)
    application = _owned_application(interview.application_id, current_user.id, db)
    answer = _answer_for_interview(answer_id, interview.id, db)
    question = db.scalar(select(InterviewQuestion).where(
        InterviewQuestion.id == answer.question_id, InterviewQuestion.interview_id == interview.id
    ))
    if not question:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Answer question is no longer available")

    generated: GeneratedAnswerEvaluation = await evaluate_answer_for_application(
        application=application, interview=interview, question=question, answer=answer, resume_db=resume_db,
    )
    evaluation = db.scalar(select(InterviewAnswerEvaluation).where(InterviewAnswerEvaluation.answer_id == answer.id))
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
    db.commit()
    db.refresh(evaluation)
    return APIResponse(success=True, data=_evaluation_data(evaluation), error=None)


@router.get("", response_model=APIResponse)
def list_interviews(
    db: DbSession, current_user: PremiumUser,
    application_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
):
    filters = [Application.user_id == current_user.id, Application.is_scratch.is_(False)]
    if application_id is not None:
        filters.append(Interview.application_id == application_id)
    if status_filter is not None:
        filters.append(Interview.status == status_filter)

    base_query = select(Interview).join(Application, Interview.application_id == Application.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    interviews = db.scalars(
        base_query.order_by(Interview.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
        .options(selectinload(Interview.questions))
    ).all()

    interview_ids = [interview.id for interview in interviews]
    aggregates: dict[UUID, tuple[int, float, float]] = {}
    if interview_ids:
        for interview_id_, answered_count, average_score, average_confidence in db.execute(
            select(
                InterviewAnswer.interview_id,
                func.count(InterviewAnswerEvaluation.id),
                func.avg(InterviewAnswerEvaluation.overall_score),
                func.avg(InterviewAnswerEvaluation.confidence_score),
            )
            .join(InterviewAnswerEvaluation, InterviewAnswerEvaluation.answer_id == InterviewAnswer.id)
            .where(InterviewAnswer.interview_id.in_(interview_ids))
            .group_by(InterviewAnswer.interview_id)
        ).all():
            aggregates[interview_id_] = (answered_count, average_score, average_confidence)

    items = []
    for interview in interviews:
        answered_count, average_score, average_confidence = aggregates.get(interview.id, (0, None, None))
        items.append(InterviewSummaryData(
            interview_id=interview.id, application_id=interview.application_id, personality=interview.personality,
            difficulty=interview.difficulty, status=interview.status, question_count=len(interview.questions),
            question_target=interview.question_target,
            answered_count=answered_count, average_score=average_score, average_confidence=average_confidence,
            started_at=interview.started_at, completed_at=interview.completed_at, created_at=interview.created_at,
            recommendation=interview.recommendation,
        ))
    return APIResponse(
        success=True, data=InterviewHistoryData(items=items, total=total, page=page, page_size=page_size), error=None,
    )


@router.get("/{interview_id}/full", response_model=APIResponse)
def get_interview_full(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = db.scalar(
        select(Interview)
        .join(Application, Interview.application_id == Application.id)
        .where(
            Interview.id == interview_id,
            Application.user_id == current_user.id,
            Application.is_scratch.is_(False),
        )
        .options(
            selectinload(Interview.questions)
            .selectinload(InterviewQuestion.answers)
            .selectinload(InterviewAnswer.evaluation)
        )
    )
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    items = []
    scores: list[int] = []
    confidences: list[int] = []
    for question in interview.questions:
        answer = question.answers[0] if question.answers else None
        evaluation = answer.evaluation if answer else None
        if evaluation is not None:
            scores.append(evaluation.overall_score)
            confidences.append(evaluation.confidence_score)
        items.append(InterviewQuestionWithAnswerData(
            question=_question_data(question),
            answer=_answer_data(answer) if answer else None,
            evaluation=_evaluation_data(evaluation) if evaluation else None,
        ))
    return APIResponse(success=True, data=InterviewFullSessionData(
        interview_id=interview.id, application_id=interview.application_id, personality=interview.personality,
        difficulty=interview.difficulty, status=interview.status, question_target=interview.question_target,
        started_at=interview.started_at,
        completed_at=interview.completed_at, created_at=interview.created_at, summary=interview.summary,
        recommendation=interview.recommendation,
        average_score=(sum(scores) / len(scores)) if scores else None,
        average_confidence=(sum(confidences) / len(confidences)) if confidences else None,
        items=items,
    ), error=None)


@router.post("/{interview_id}/complete", response_model=APIResponse)
async def complete_interview(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = _owned_interview(interview_id, current_user.id, db)
    application = _owned_application(interview.application_id, current_user.id, db)
    if interview.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This interview session is already completed")

    question_count = db.scalar(select(func.count()).where(InterviewQuestion.interview_id == interview.id)) or 0
    evaluations = db.scalars(
        select(InterviewAnswerEvaluation)
        .join(InterviewAnswer, InterviewAnswerEvaluation.answer_id == InterviewAnswer.id)
        .where(InterviewAnswer.interview_id == interview.id)
    ).all()
    answered_count = len(evaluations)
    average_score = (sum(e.overall_score for e in evaluations) / answered_count) if answered_count else 0.0
    average_confidence = (sum(e.confidence_score for e in evaluations) / answered_count) if answered_count else 0.0
    all_weaknesses = list(dict.fromkeys(w for e in evaluations for w in e.weaknesses))
    all_missing_points = list(dict.fromkeys(m for e in evaluations for m in e.missing_points))
    all_strengths = list(dict.fromkeys(s for e in evaluations for s in e.strengths))

    generated = summarize_interview_for_application(
        application=application, interview=interview, question_count=question_count,
        answered_count=answered_count, average_score=average_score, average_confidence=average_confidence,
        all_weaknesses=all_weaknesses, all_missing_points=all_missing_points, all_strengths=all_strengths,
    )
    interview.status = "completed"
    interview.completed_at = datetime.now(timezone.utc)
    interview.summary = generated.summary
    interview.recommendation = generated.recommendation.value
    db.commit()
    return APIResponse(success=True, data=CompleteInterviewData(
        interview_id=interview.id, status=interview.status, completed_at=interview.completed_at,
        question_count=question_count, answered_count=answered_count,
        average_score=average_score if answered_count else None,
        average_confidence=average_confidence if answered_count else None,
        summary=interview.summary, recommendation=interview.recommendation,
    ), error=None)


@router.delete("/{interview_id}", response_model=APIResponse)
def delete_interview(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = _owned_interview(interview_id, current_user.id, db)
    db.delete(interview)
    db.commit()
    return APIResponse(success=True, data=None, error=None)
