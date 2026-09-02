"""ISSUE-15 — JD <-> resume skill matching. Pure functions, taxonomy-aware
(so "AWS" vs "Amazon Web Services" still match), used by ats_engine.py."""
from app.services.taxonomy import dedupe_normalized


def match_skills(resume_skills: list[str], jd_skills: list[str]) -> tuple[list[str], list[str]]:
    """Returns (matched_skills, missing_skills), both normalized to
    canonical taxonomy names and de-duplicated, preserving the JD's
    original ordering (missing/matched skills are usually displayed in JD
    priority order)."""
    resume_norm = {s.lower() for s in dedupe_normalized(resume_skills)}
    jd_norm = dedupe_normalized(jd_skills)

    matched = [s for s in jd_norm if s.lower() in resume_norm]
    missing = [s for s in jd_norm if s.lower() not in resume_norm]
    return matched, missing


def skill_overlap_ratio(resume_skills: list[str], jd_skills: list[str]) -> float:
    if not jd_skills:
        return 1.0
    matched, _ = match_skills(resume_skills, jd_skills)
    return len(matched) / len(dedupe_normalized(jd_skills))
