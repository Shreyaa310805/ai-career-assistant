from fastapi import APIRouter

from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse
)

from app.services.recommendation_service import (
    get_learning_recommendations
)


router = APIRouter(
    prefix="/api/v1/career",
    tags=["Learning Recommendations"]
)


@router.post(
    "/recommendations",
    response_model=RecommendationResponse
)
def get_recommendations(data: RecommendationRequest):

    result = get_learning_recommendations(
        application_id=data.application_id,
        skills=data.skills
    )

    return result