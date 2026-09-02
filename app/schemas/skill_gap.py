from pydantic import BaseModel
from typing import List


class SkillGapRequest(BaseModel):
    application_id: str
    required_skills: List[str]
    user_skills: List[str]


class SkillGapResponse(BaseModel):
    application_id: str
    matched_skills: List[str]
    missing_skills: List[str]
    extra_skills: List[str]
    skill_gap_count: int