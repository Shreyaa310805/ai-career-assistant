from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, PremiumUser
from app.models.application import Application
from app.models.interview import Interview
from app.schemas.interview import APIResponse, InterviewCreateRequest, InterviewData

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _interview_data(interview: Interview) -> InterviewData:
    return InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=0,
        started_at=interview.started_at,
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
