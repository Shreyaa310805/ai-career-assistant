"""
ISSUE-17 — Resume version storage (next-version-number helper; storage
itself is a plain insert done in the route handler).
ISSUE-18 — Resume version comparison.
ISSUE-19 — Best-version selection.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import AtsReport, Resume
from app.schemas.resume import ParsedResumeData, VersionDiff


async def next_version_number(db: AsyncSession, application_id: str) -> int:
    result = await db.execute(
        select(Resume.version_number)
        .where(Resume.application_id == application_id)
        .order_by(Resume.version_number.desc())
        .limit(1)
    )
    current_max = result.scalar_one_or_none()
    return (current_max or 0) + 1


async def get_latest_ats_report(db: AsyncSession, resume_id: str) -> AtsReport | None:
    result = await db.execute(
        select(AtsReport)
        .where(AtsReport.resume_id == resume_id)
        .order_by(AtsReport.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


def diff_versions(
    parsed_v1: ParsedResumeData,
    parsed_v2: ParsedResumeData,
    ats_v1: AtsReport | None,
    ats_v2: AtsReport | None,
) -> VersionDiff:
    skills_v1 = {s.lower(): s for s in parsed_v1.skills}
    skills_v2 = {s.lower(): s for s in parsed_v2.skills}

    skills_gained = [skills_v2[k] for k in skills_v2 if k not in skills_v1]
    skills_lost = [skills_v1[k] for k in skills_v1 if k not in skills_v2]

    edu_v1 = {e.lower() for e in parsed_v1.education}
    edu_v2 = {e.lower() for e in parsed_v2.education}
    education_gained = [e for e in parsed_v2.education if e.lower() not in edu_v1]
    education_lost = [e for e in parsed_v1.education if e.lower() not in edu_v2]

    ats_delta = None
    match_delta = None
    if ats_v1 is not None and ats_v2 is not None:
        ats_delta = round(ats_v2.ats_score - ats_v1.ats_score, 2)
        match_delta = round(ats_v2.match_score - ats_v1.match_score, 2)

    return VersionDiff(
        skills_gained=skills_gained,
        skills_lost=skills_lost,
        experience_years_delta=round(
            parsed_v2.experience_years - parsed_v1.experience_years, 2
        ),
        ats_score_delta=ats_delta,
        match_score_delta=match_delta,
        education_gained=education_gained,
        education_lost=education_lost,
        work_history_count_delta=len(parsed_v2.work_history) - len(parsed_v1.work_history),
    )


def recommend_version(
    diff: VersionDiff, ats_v1: AtsReport | None, ats_v2: AtsReport | None
) -> tuple[str, str]:
    """Returns (recommended_version, reason). Prefers actual ATS/match
    scores when both versions have been analyzed; otherwise falls back to
    a structural heuristic (net skills gained, experience delta)."""
    if ats_v1 is not None and ats_v2 is not None:
        combined_v1 = ats_v1.ats_score + ats_v1.match_score
        combined_v2 = ats_v2.ats_score + ats_v2.match_score
        if combined_v2 > combined_v1:
            return "v2", (
                f"v2 has a higher combined ATS+match score "
                f"({combined_v2:.1f} vs {combined_v1:.1f})."
            )
        if combined_v1 > combined_v2:
            return "v1", (
                f"v1 has a higher combined ATS+match score "
                f"({combined_v1:.1f} vs {combined_v2:.1f})."
            )
        return "tie", "Both versions have identical combined ATS+match scores."

    net_skill_change = len(diff.skills_gained) - len(diff.skills_lost)
    if net_skill_change > 0 or diff.experience_years_delta > 0:
        return "v2", (
            "v2 shows more skills and/or experience than v1 "
            "(no ATS report available yet to compare scores directly)."
        )
    if net_skill_change < 0 or diff.experience_years_delta < 0:
        return "v1", (
            "v1 shows more skills and/or experience than v2 "
            "(no ATS report available yet to compare scores directly)."
        )
    return "tie", "No meaningful structural difference detected between versions."
