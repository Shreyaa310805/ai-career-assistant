from fastapi import APIRouter

from app.schemas.priority import (
    SkillPriorityRequest,
    SkillPriorityResponse
)

from app.services.priority_service import calculate_priority


router = APIRouter(
    prefix="/api/v1/career",
    tags=["Skill Priority"]
)


@router.post(
    "/skill-priority",
    response_model=SkillPriorityResponse
)
def get_skill_priority(data: SkillPriorityRequest):

    result = calculate_priority(
        application_id=data.application_id,
        skills=data.skills
    )

    return result