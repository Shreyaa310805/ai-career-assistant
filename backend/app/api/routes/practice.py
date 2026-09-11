"""Person 4 entry point; keeps Person 2's required application_id contract intact."""
from fastapi import APIRouter, Header, HTTPException
from typing import Annotated
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession
from app.api.routes.interviews import create_interview, _interview_data
from app.models.application import Application
from app.models.interview import Interview
from app.models.subscription import InterviewUsage
from app.schemas.interview import APIResponse, DifficultyEnum, InterviewCreateRequest, PersonalityEnum
from app.services.entitlements import lock_user, started_interview

router = APIRouter(prefix="/practice", tags=["practice"])


class PracticeRequest(BaseModel):
    personality: PersonalityEnum = PersonalityEnum.technical
    difficulty: DifficultyEnum = DifficultyEnum.medium


@router.post("/interviews", response_model=APIResponse)
def start_practice(payload: PracticeRequest, db: DbSession, current_user: CurrentUser,
                   idempotency_key: Annotated[UUID | None, Header()] = None):
    lock_user(db, current_user.id)
    existing = started_interview(db, current_user.id, idempotency_key)
    if existing:
        if existing.personality != payload.personality.value or existing.difficulty != payload.difficulty.value:
            raise HTTPException(409, "Idempotency key was used with different interview options")
        return APIResponse(success=True, data=_interview_data(existing), error=None)
    application = Application(user_id=current_user.id, company="Practice", role="Software Engineer", is_scratch=True)
    db.add(application)
    db.flush()
    return create_interview(InterviewCreateRequest(application_id=application.id, **payload.model_dump()), db, current_user, idempotency_key)


@router.get("/interviews")
def history(db: DbSession, current_user: CurrentUser):
    sessions = db.execute(select(Interview, InterviewUsage.credits_charged).join(Application)
        .outerjoin(InterviewUsage, InterviewUsage.interview_id == Interview.id)
        .where(Application.user_id == current_user.id).order_by(Interview.created_at.desc()).limit(100)).all()
    return {"success": True, "data": [{"session": _interview_data(s), "is_trial": s.is_trial,
        "credits_charged": charged or 0} for s, charged in sessions], "error": None}
