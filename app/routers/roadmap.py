from fastapi import APIRouter, HTTPException

from app.schemas.roadmap import RoadmapResponse
from app.services.roadmap_service import generate_career_roadmap


router = APIRouter(
    prefix="/api/v1/career",
    tags=["Career Roadmap"]
)


@router.get(
    "/roadmap/{application_id}",
    response_model=RoadmapResponse
)
def get_career_roadmap(application_id: str):

    result = generate_career_roadmap(application_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return result