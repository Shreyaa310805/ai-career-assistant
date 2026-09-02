from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    application_id: str
    skill: str
    current_match_score: float = Field(ge=0, le=100)
    job_importance: float = Field(ge=0, le=1)
    current_level: float = Field(ge=0, le=1)
    target_level: float = Field(ge=0, le=1)


class WhatIfResponse(BaseModel):
    application_id: str
    skill: str
    current_level: float
    target_level: float
    current_match_score: float
    estimated_match_score: float
    estimated_improvement: float
    impact: str
    message: str