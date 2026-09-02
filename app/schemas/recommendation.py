from typing import List
from pydantic import BaseModel


class SkillRecommendationInput(BaseModel):
    skill: str
    priority: str


class RecommendationRequest(BaseModel):
    application_id: str
    skills: List[SkillRecommendationInput]


class LearningResource(BaseModel):
    title: str
    type: str
    provider: str
    difficulty: str
    url: str
    source: str


class SkillRecommendation(BaseModel):
    skill: str
    priority: str
    resources: List[LearningResource]


class RecommendationResponse(BaseModel):
    application_id: str
    recommendations: List[SkillRecommendation]