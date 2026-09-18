"""ISSUE-15 — JD <-> resume skill matching. Pure functions, taxonomy-aware
(so "AWS" vs "Amazon Web Services" still match), used by ats_engine.py.

Matching runs in three tiers so that skills the taxonomy has never seen still
compare sensibly:

  1. canonical equality      "AWS" == "Amazon Web Services"  (synonym map)
  2. token-set equality      "React JS" == "react.js"        (punctuation/order)
  3. close string similarity "Snowflake" ~= "Snowflakes"     (ratio >= 0.87)

Tier 3 is deliberately tight — loose fuzzy matching would credit a candidate
for skills they do not have, which is worse than a false miss.
"""
import re
from difflib import SequenceMatcher

from app.services.resumes.taxonomy import dedupe_normalized

SIMILARITY_THRESHOLD = 0.87

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
# Suffixes that carry no meaning when comparing technology names.
_NOISE_TOKENS = {"js", "lang", "language", "framework", "library", "db"}


def _tokens(skill: str) -> frozenset[str]:
    parts = [p for p in _TOKEN_SPLIT_RE.split(skill.lower()) if p]
    meaningful = frozenset(p for p in parts if p not in _NOISE_TOKENS)
    return meaningful or frozenset(parts)


def _flat(skill: str) -> str:
    return _TOKEN_SPLIT_RE.sub("", skill.lower())


def skills_equivalent(left: str, right: str) -> bool:
    """True when two canonical skill names denote the same skill."""
    if left.lower() == right.lower():
        return True
    if _tokens(left) == _tokens(right):
        return True
    left_flat, right_flat = _flat(left), _flat(right)
    if not left_flat or not right_flat:
        return False
    if left_flat == right_flat:
        return True
    # Very short names ("go", "r", "c#") are too collision-prone to fuzz.
    if min(len(left_flat), len(right_flat)) < 4:
        return False
    return SequenceMatcher(None, left_flat, right_flat).ratio() >= SIMILARITY_THRESHOLD


def match_skills(resume_skills: list[str], jd_skills: list[str]) -> tuple[list[str], list[str]]:
    """Returns (matched_skills, missing_skills), both normalized to
    canonical taxonomy names and de-duplicated, preserving the JD's
    original ordering (missing/matched skills are usually displayed in JD
    priority order)."""
    resume_norm = dedupe_normalized(resume_skills)
    jd_norm = dedupe_normalized(jd_skills)

    # Exact canonical hits are cheap; only unresolved JD skills pay for tiers 2-3.
    resume_exact = {s.lower() for s in resume_norm}

    matched: list[str] = []
    missing: list[str] = []
    for jd_skill in jd_norm:
        if jd_skill.lower() in resume_exact or any(
            skills_equivalent(jd_skill, resume_skill) for resume_skill in resume_norm
        ):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)
    return matched, missing


def skill_overlap_ratio(resume_skills: list[str], jd_skills: list[str]) -> float:
    if not jd_skills:
        return 1.0
    matched, _ = match_skills(resume_skills, jd_skills)
    return len(matched) / len(dedupe_normalized(jd_skills))
