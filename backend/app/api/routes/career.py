from uuid import UUID
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, PremiumUser
from app.db.resume_session import get_db
from app.models.application import Application
from app.models.resume import AtsReport, Resume
from app.services.resumes.matching import alternative_skill_groups

# Career intelligence (roadmap, skill gap, priorities, what-if, learning) is a
# PREMIUM feature, enforced here rather than in the client.
router = APIRouter(prefix="/career", tags=["career"])

LOW_PROFICIENCY = 0.33
MEDIUM_PROFICIENCY = 0.66
HIGH_PROFICIENCY = 1.0
PROFICIENCY_LEVELS = (LOW_PROFICIENCY, MEDIUM_PROFICIENCY, HIGH_PROFICIENCY)
PROFICIENCY_LABELS = {
    LOW_PROFICIENCY: "Low",
    MEDIUM_PROFICIENCY: "Medium",
    HIGH_PROFICIENCY: "High",
}


class WhatIfRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=120)
    target_level: float = Field(ge=0, le=1)


def _skill_map(skills: list[str]) -> dict[str, str]:
    return {skill.strip().lower(): skill.strip() for skill in skills if skill and skill.strip()}


# Priority score bounds: the first gap in the job description scores TOP,
# the last scores BOTTOM, evenly spaced in between. Alternatives that another
# option already covers sit below every real gap at COVERED.
_PRIORITY_TOP = 0.9
_PRIORITY_BOTTOM = 0.5
_PRIORITY_COVERED = 0.1


def _priority_label(score: float) -> str:
    return "High" if score >= 0.7 else "Medium" if score >= 0.4 else "Low"


def _priority_for_missing_skills(
    skills: list[str],
    role: str,
    jd_text: str = "",
    covered: dict[str, list[str]] | None = None,
) -> list[dict[str, object]]:
    """Rank gaps by their position in the job description.

    The ATS report keeps missing skills in JD order, and a requirement nearer
    the top is normally a stronger signal of role relevance, so position is
    the transparent, reproducible importance proxy:

        priority_score = 0.9 - 0.4 × k / (N - 1)

    where N is the number of missing *requirements* and k (0-based) is this
    requirement's position. A requirement written as alternatives ("Go,
    Python or Java") is ONE requirement, so all its options share the same k
    and therefore the same score — none is penalised for coming later in the
    sentence.

    `covered` holds alternatives whose requirement the resume already meets
    through another option (skill -> the options held). They are not gaps:
    they are listed after every real gap with the lowest score.
    """
    groups = alternative_skill_groups(jd_text, skills) if jd_text else []
    group_of = {member.strip().lower(): index for index, group in enumerate(groups) for member in group}

    # Requirement units in JD order; an alternative group takes the slot of
    # its first member.
    units: list[list[str]] = []
    unit_of_group: dict[int, int] = {}
    for skill in skills:
        group = group_of.get(skill.strip().lower())
        if group is None:
            units.append([skill])
        elif group in unit_of_group:
            units[unit_of_group[group]].append(skill)
        else:
            unit_of_group[group] = len(units)
            units.append([skill])

    last = max(len(units) - 1, 1)
    result = []
    for position, unit in enumerate(units):
        # Missing skills have a current level of 0, so importance is the score.
        score = round(_PRIORITY_TOP - (_PRIORITY_TOP - _PRIORITY_BOTTOM) * position / last, 2)
        for skill in unit:
            reason = (
                f"{skill} is a missing requirement from the ATS analysis for {role} "
                f"(requirement {position + 1} of {len(units)} in job-description order)."
            )
            others = [other for other in unit if other != skill]
            if others:
                reason += (
                    " The job description accepts it interchangeably with "
                    + ", ".join(others)
                    + ", so every option has equal priority and learning any one closes this gap."
                )
            result.append({
                "skill": skill,
                "priority": _priority_label(score),
                "priority_score": score,
                "reason": reason,
            })

    listed = {skill.strip().lower() for skill in skills}
    for skill, held in (covered or {}).items():
        if skill.strip().lower() in listed:
            continue
        result.append({
            "skill": skill,
            "priority": _priority_label(_PRIORITY_COVERED),
            "priority_score": _PRIORITY_COVERED,
            "reason": (
                f"Optional: the job description accepts {skill} or {', '.join(held)}, and your "
                f"resume already has {', '.join(held)}, so this requirement is met. Lowest priority."
            ),
        })
    return result


def _covered_alternatives(
    report: AtsReport, missing: list[str], user_skills: dict[str, str], jd_text: str
) -> dict[str, list[str]]:
    """Missing skills whose "X or Y" requirement the resume already meets.

    Recomputed from the job description at read time (not only taken from the
    stored report), so reports analysed before alternatives were detected are
    corrected too. Maps each such skill to the alternatives the resume holds.
    """
    covered: dict[str, list[str]] = {
        skill: list(held)
        for skill, held in ((report.score_breakdown or {}).get("covered_alternatives") or {}).items()
    }
    if not jd_text.strip():
        return covered
    held_keys = set(user_skills) | {skill.strip().lower() for skill in report.matched_skills}
    jd_skills = [*report.matched_skills, *report.missing_skills, *covered]
    for group in alternative_skill_groups(jd_text, jd_skills):
        held = [member for member in group if member.strip().lower() in held_keys]
        if not held:
            continue
        for skill in missing:
            if skill.strip().lower() in {member.strip().lower() for member in group} and skill not in held:
                covered[skill] = held
    return covered


# A curated starting point per skill: documentation first, then something
# hands-on. Kept server-side and static so the roadmap never depends on an
# external API being reachable.
_LEARNING_CATALOG: dict[str, list[dict[str, str]]] = {
    "python": [
        {"title": "Python Official Tutorial", "provider": "Python", "difficulty": "beginner", "type": "documentation", "url": "https://docs.python.org/3/tutorial/"},
        {"title": "Python Practice Problems", "provider": "HackerRank", "difficulty": "intermediate", "type": "practice", "url": "https://www.hackerrank.com/domains/python"},
    ],
    "fastapi": [
        {"title": "FastAPI Official Tutorial", "provider": "FastAPI", "difficulty": "beginner", "type": "documentation", "url": "https://fastapi.tiangolo.com/tutorial/"},
        {"title": "Build REST APIs with FastAPI", "provider": "FastAPI", "difficulty": "intermediate", "type": "project", "url": "https://fastapi.tiangolo.com/advanced/"},
    ],
    "docker": [
        {"title": "Docker Get Started", "provider": "Docker", "difficulty": "beginner", "type": "tutorial", "url": "https://docs.docker.com/get-started/"},
        {"title": "Docker 101 Tutorial", "provider": "Docker", "difficulty": "intermediate", "type": "course", "url": "https://www.docker.com/101-tutorial/"},
    ],
    "aws": [
        {"title": "AWS Cloud Practitioner Essentials", "provider": "AWS", "difficulty": "beginner", "type": "course", "url": "https://aws.amazon.com/training/digital/aws-cloud-practitioner-essentials/"},
        {"title": "AWS Documentation", "provider": "AWS", "difficulty": "intermediate", "type": "documentation", "url": "https://docs.aws.amazon.com/"},
    ],
    "postgresql": [
        {"title": "PostgreSQL Tutorial", "provider": "PostgreSQL", "difficulty": "beginner", "type": "documentation", "url": "https://www.postgresql.org/docs/current/tutorial.html"},
        {"title": "PostgreSQL Exercises", "provider": "pgexercises", "difficulty": "intermediate", "type": "practice", "url": "https://pgexercises.com/"},
    ],
    "kubernetes": [
        {"title": "Kubernetes Basics", "provider": "Kubernetes", "difficulty": "beginner", "type": "tutorial", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/"},
    ],
    "javascript": [
        {"title": "JavaScript Guide", "provider": "MDN", "difficulty": "beginner", "type": "documentation", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"},
    ],
    "typescript": [
        {"title": "TypeScript Handbook", "provider": "TypeScript", "difficulty": "beginner", "type": "documentation", "url": "https://www.typescriptlang.org/docs/handbook/intro.html"},
    ],
    "react": [
        {"title": "React Learn", "provider": "React", "difficulty": "beginner", "type": "documentation", "url": "https://react.dev/learn"},
        {"title": "React Tutorial: Tic-Tac-Toe", "provider": "React", "difficulty": "beginner", "type": "project", "url": "https://react.dev/learn/tutorial-tic-tac-toe"},
    ],
    "sql": [
        {"title": "SQL Tutorial", "provider": "PostgreSQL", "difficulty": "beginner", "type": "documentation", "url": "https://www.postgresql.org/docs/current/tutorial.html"},
        {"title": "SQL Practice", "provider": "HackerRank", "difficulty": "intermediate", "type": "practice", "url": "https://www.hackerrank.com/domains/sql"},
    ],
    "git": [
        {"title": "Pro Git Book", "provider": "Git", "difficulty": "beginner", "type": "documentation", "url": "https://git-scm.com/book/en/v2"},
    ],
    "terraform": [
        {"title": "Terraform Tutorials", "provider": "HashiCorp", "difficulty": "beginner", "type": "tutorial", "url": "https://developer.hashicorp.com/terraform/tutorials"},
    ],
    "ci/cd": [
        {"title": "GitHub Actions Documentation", "provider": "GitHub", "difficulty": "beginner", "type": "documentation", "url": "https://docs.github.com/en/actions"},
    ],
}


def _learning_resources(skill: str) -> list[dict[str, str]]:
    """Return a useful, stable starting point without calling an external API."""
    curated = _LEARNING_CATALOG.get(skill.strip().lower())
    resources = list(curated) if curated else [{
        "title": f"Learn {skill.strip()}",
        "provider": "Google",
        "difficulty": "beginner",
        "type": "tutorial",
        "url": f"https://www.google.com/search?q={quote_plus(skill.strip())}",
    }]
    query = quote_plus(f"{skill.strip()} tutorial")
    resources.append({
        "title": f"Popular YouTube tutorials: {skill.strip()}",
        "provider": "YouTube",
        "difficulty": "beginner",
        "type": "video",
        "url": f"https://www.youtube.com/results?search_query={query}",
    })
    return resources


async def _load_career_data(application_id: UUID, current_user: PremiumUser, application_db: DbSession, resume_db: AsyncSession):
    application = application_db.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
            Application.is_scratch.is_(False),
        )
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    resumes = await resume_db.execute(
        select(Resume).where(Resume.application_id == str(application_id)).order_by(Resume.is_best_version.desc(), Resume.created_at.desc())
    )
    resume = resumes.scalars().first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload a resume for this application first")

    reports = await resume_db.execute(
        select(AtsReport).where(AtsReport.resume_id == resume.id).order_by(AtsReport.created_at.desc())
    )
    report = reports.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run ATS analysis for this resume first")
    return application, resume, report


@router.get("/roadmap/{application_id}")
async def get_career_roadmap(
    application_id: UUID,
    current_user: PremiumUser,
    application_db: DbSession,
    resume_db: AsyncSession = Depends(get_db),
):
    application, resume, report = await _load_career_data(application_id, current_user, application_db, resume_db)

    user_skills = _skill_map(resume.parsed_data.get("skills", []))
    required_skills = _skill_map([*report.matched_skills, *report.missing_skills])
    matched = sorted(required_skills[key] for key in required_skills.keys() & user_skills.keys())
    # Preserve the ATS/JD order: it is the only persisted signal available
    # for relative requirement importance.
    missing = [skill for skill in report.missing_skills if skill.strip().lower() in required_skills and skill.strip().lower() not in user_skills]
    extra = sorted(user_skills[key] for key in user_skills.keys() - required_skills.keys())

    jd_text = application.job_description or ""
    covered = _covered_alternatives(report, missing, user_skills, jd_text)
    missing = [skill for skill in missing if skill not in covered]
    prioritized_skills = _priority_for_missing_skills(
        missing, application.role, jd_text, covered
    )
    recommendations = [
        {"skill": item["skill"], "priority": item["priority"], "resources": _learning_resources(str(item["skill"]))}
        for item in prioritized_skills
    ]

    return {
        "application_id": str(application_id), "company": application.company, "role": application.role,
        "current_match_score": round(report.match_score),
        "skill_gap": {"matched_skills": matched, "missing_skills": missing, "extra_skills": extra, "skill_gap_count": len(missing)},
        "prioritized_skills": prioritized_skills, "recommendations": recommendations,
    }


@router.post("/what-if/{application_id}")
async def simulate_what_if(
    application_id: UUID,
    payload: WhatIfRequest,
    current_user: PremiumUser,
    application_db: DbSession,
    resume_db: AsyncSession = Depends(get_db),
):
    """Estimate a gain for a real ATS gap without trusting client-side scores."""
    application, resume, report = await _load_career_data(application_id, current_user, application_db, resume_db)
    required = _skill_map([*report.missing_skills, *report.matched_skills])
    matched = _skill_map(report.matched_skills)
    skill_key = payload.skill.strip().lower()
    if skill_key not in required:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a skill required by this ATS analysis")

    ordered_required = list(required)
    importance = _priority_for_missing_skills(
        [required[key] for key in ordered_required],
        application.role,
        application.job_description or "",
    )[ordered_required.index(skill_key)]["priority_score"]
    # The ATS report only evidences whether a role skill is present.  Present
    # skills start at Medium; missing requirements start at Low.
    current_level = MEDIUM_PROFICIENCY if skill_key in matched else LOW_PROFICIENCY
    if payload.target_level not in PROFICIENCY_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Choose Low, Medium, or High as the target proficiency level",
        )
    if payload.target_level <= current_level:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a proficiency level above the current level")
    improvement = round(float(importance) * (payload.target_level - current_level) * 20, 2)
    estimated_match = round(min(report.match_score + improvement, 100), 2)
    impact = "High" if improvement >= 10 else "Medium" if improvement >= 5 else "Low"
    return {
        "application_id": str(application_id), "skill": required[skill_key], "current_level": current_level,
        "target_level": payload.target_level, "current_match_score": round(report.match_score, 2),
        "estimated_match_score": estimated_match, "estimated_improvement": improvement,
        "impact": impact,
        "message": f"Improving {required[skill_key]} from {PROFICIENCY_LABELS[current_level]} to {PROFICIENCY_LABELS[payload.target_level]} proficiency is estimated to improve this role match by {improvement} points.",
    }
