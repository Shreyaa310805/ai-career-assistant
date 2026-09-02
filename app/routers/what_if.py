from fastapi import APIRouter

from app.schemas.what_if import (
    WhatIfRequest,
    WhatIfResponse
)

from app.services.what_if_service import simulate_what_if


router = APIRouter(
    prefix="/api/v1/career",
    tags=["What-If Simulation"]
)


@router.post(
    "/what-if",
    response_model=WhatIfResponse
)
def run_what_if_simulation(data: WhatIfRequest):

    result = simulate_what_if(
        application_id=data.application_id,
        skill=data.skill,
        current_match_score=data.current_match_score,
        job_importance=data.job_importance,
        current_level=data.current_level,
        target_level=data.target_level
    )

    return result