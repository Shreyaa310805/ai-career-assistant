from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from database import get_db
from models import Interview
from schemas import InterviewCreateRequest, InterviewData, APIResponse

router = APIRouter(prefix="/api/v1/interviews", tags=["interviews"])


@router.post("", response_model=APIResponse)
def create_interview(payload: InterviewCreateRequest, db: Session = Depends(get_db)):
    interview = Interview(
        application_id=payload.application_id,
        personality=payload.personality.value,
        difficulty=payload.difficulty.value,
        status="created",
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    data = InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=0,
        started_at=interview.started_at,
    )
    return APIResponse(success=True, data=data, error=None)


@router.get("/{interview_id}", response_model=APIResponse)
def get_interview(interview_id: uuid.UUID, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()

    if not interview:
        return APIResponse(
            success=False,
            data=None,
            error={
                "code": "INTERVIEW_NOT_FOUND",
                "message": f"No interview found with id {interview_id}",
                "details": None,
            },
        )

    data = InterviewData(
        interview_id=interview.id,
        application_id=interview.application_id,
        personality=interview.personality,
        difficulty=interview.difficulty,
        status=interview.status,
        question_count=0,
        started_at=interview.started_at,
    )
    return APIResponse(success=True, data=data, error=None)