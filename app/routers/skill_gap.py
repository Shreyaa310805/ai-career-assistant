from fastapi import APIRouter
from app.schemas.skill_gap import SkillGapRequest, SkillGapResponse
from app.services.skill_gap_service import analyze_skill_gap


router = APIRouter(
    prefix="/api/v1/career",
    tags=["Skill Gap"]
)


@router.post(
    "/skill-gap",
    response_model=SkillGapResponse
)
def get_skill_gap(data: SkillGapRequest):
    result = analyze_skill_gap(
        application_id=data.application_id,
        required_skills=data.required_skills,
        user_skills=data.user_skills
    )

    return result