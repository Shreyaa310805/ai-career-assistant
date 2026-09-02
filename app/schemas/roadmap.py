from typing import List
from pydantic import BaseModel

from app.schemas.priority import PrioritizedSkill
from app.schemas.recommendation import SkillRecommendation


class SkillGapSummary(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]
    skill_gap_count: int


class RoadmapResponse(BaseModel):
    application_id: str
    company: str
    role: str
    current_match_score: float

    skill_gap: SkillGapSummary

    prioritized_skills: List[PrioritizedSkill]

    recommendations: List[SkillRecommendation]