from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, PremiumUser
from app.db.resume_session import get_db
from app.models.application import Application
from app.models.resume import AtsReport, Resume

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


def _priority_for_missing_skills(skills: list[str], role: str) -> list[dict[str, object]]:
    """Rank gaps using their order in the ATS analysis, not placeholder data.

    The ATS report preserves the job-description order of required skills.  A
    skill nearer the top is normally a stronger signal of role relevance, so
    we use that order as a transparent, reproducible importance proxy.
    """
    total = max(len(skills), 1)
    result = []
    for index, skill in enumerate(skills):
        importance = 0.9 - (0.4 * index / max(total - 1, 1))
        score = round(importance, 2)  # missing skills have a current level of 0
        priority = "High" if score >= 0.7 else "Medium" if score >= 0.4 else "Low"
        result.append({
            "skill": skill,
            "priority": priority,
            "priority_score": score,
            "reason": f"{skill} is a missing requirement from the ATS analysis for {role}.",
        })
    return result


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
    if curated:
        return curated
    query = skill.strip().replace(" ", "+")
    return [
        {
            "title": f"Learn {skill.strip()}",
            "provider": "Web search",
            "difficulty": "beginner",
            "type": "documentation",
            "url": f"https://www.google.com/search?q={query}+official+documentation",
        }
    ]


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

    prioritized_skills = _priority_for_missing_skills(missing, application.role)
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
    importance = _priority_for_missing_skills([required[key] for key in ordered_required], application.role)[ordered_required.index(skill_key)]["priority_score"]
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
