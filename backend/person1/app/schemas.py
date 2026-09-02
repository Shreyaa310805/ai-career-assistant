"""Pydantic v2 schemas: parsed resume/JD structures, API request bodies,
and API response payloads (the `data` object inside the standard
{success,data,error} envelope)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Structured resume/JD data (ISSUE-13) — this is also the JSON schema handed
# to Gemini for structured output, and the shape the heuristic fallback
# parser must produce.
# ---------------------------------------------------------------------------
class WorkHistoryItem(BaseModel):
    company: str = ""
    role: str = ""
    duration: str = ""
    bullets: list[str] = Field(default_factory=list)


class ParsedResumeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_name: str = ""
    email: str = ""
    phone: str = ""
    skills: list[str] = Field(default_factory=list)
    experience_years: float = 0.0
    work_history: list[WorkHistoryItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class ParsedJDData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role_title: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: float = 0.0
    responsibilities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Improvement suggestions (ISSUE-16)
# ---------------------------------------------------------------------------
class ImprovementSuggestion(BaseModel):
    category: str
    action: str
    impact: Literal["High", "Medium", "Low"]


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
# NOTE: POST /resumes/analyze takes multipart/form-data (application_id,
# resume_id, jd_file), not a JSON body, so it has no Pydantic request model
# here — see the `jd_file`/Form(...) parameters on the route handler itself.


class CompareRequest(BaseModel):
    resume_id_v1: str
    resume_id_v2: str


class SelectBestRequest(BaseModel):
    application_id: str
    best_resume_id: str


# ---------------------------------------------------------------------------
# Response payloads (the contents of the top-level "data" field)
# ---------------------------------------------------------------------------
class UploadResumeResponse(BaseModel):
    resume_id: str
    application_id: str
    version_number: int
    file_url: str
    raw_text: str
    parsed_data: ParsedResumeData


class AnalyzeResumeResponse(BaseModel):
    report_id: str
    application_id: str
    resume_id: str
    ats_score: float
    match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    improvement_suggestions: list[ImprovementSuggestion]


class LatestAtsSummary(BaseModel):
    report_id: str
    ats_score: float
    match_score: float
    created_at: datetime


class ResumeVersionSummary(BaseModel):
    resume_id: str
    application_id: str
    version_number: int
    file_url: str
    is_best_version: bool
    created_at: datetime
    parsed_data: ParsedResumeData
    latest_ats_report: LatestAtsSummary | None = None


class VersionListResponse(BaseModel):
    application_id: str
    versions: list[ResumeVersionSummary]


class VersionDiff(BaseModel):
    skills_gained: list[str]
    skills_lost: list[str]
    experience_years_delta: float
    ats_score_delta: float | None = None
    match_score_delta: float | None = None
    education_gained: list[str]
    education_lost: list[str]
    work_history_count_delta: int


class CompareResumesResponse(BaseModel):
    resume_v1: ResumeVersionSummary
    resume_v2: ResumeVersionSummary
    diff: VersionDiff
    recommended_version: Literal["v1", "v2", "tie"]
    recommendation_reason: str


class SelectBestResponse(BaseModel):
    application_id: str
    best_resume_id: str
    version_number: int
    updated_versions: int
