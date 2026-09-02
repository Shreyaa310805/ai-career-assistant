from typing import List
from pydantic import BaseModel


class SkillPriorityInput(BaseModel):
    skill: str
    job_importance: float
    current_level: float


class SkillPriorityRequest(BaseModel):
    application_id: str
    skills: List[SkillPriorityInput]


class PrioritizedSkill(BaseModel):
    skill: str
    priority_score: float
    priority: str
    reason: str


class SkillPriorityResponse(BaseModel):
    application_id: str
    prioritized_skills: List[PrioritizedSkill]