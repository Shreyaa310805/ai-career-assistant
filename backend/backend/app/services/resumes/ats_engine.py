"""
ISSUE-14 — ATS scoring engine.
ISSUE-16 — Explainable screening report (improvement suggestions).

`ats_score` measures how well this resume is likely to parse AND rank for
THIS SPECIFIC job description — formatting/structure quality blended with
keyword coverage against the JD actually supplied, so uploading a different
JD against the same resume must change the score.
`match_score` measures *fit against a specific JD* (skill overlap +
experience match), one layer more targeted (required vs. preferred skills,
experience gap). Both land in ats_reports per the fixed DB schema.

Every score is computed from named, inspectable sub-components so the
"explainable" requirement is met: `explain()` returns the component
breakdown, and `generate_suggestions()` turns the same signals into
concrete, actionable feedback.
"""
import re

from app.schemas.resume import ImprovementSuggestion, ParsedJDData, ParsedResumeData
from app.services.resumes.matching import match_skills
from app.services.resumes.taxonomy import dedupe_normalized

_BULLET_RE = re.compile(r"^[\s]*[-*•●▪]\s+")
_METRIC_RE = re.compile(r"\d")
_CORE_SECTION_MARKERS = ("experience", "education", "skill")


# ------------------------------------------------------------------------ #
# ats_score: resume quality BLENDED WITH keyword coverage against this JD
# ------------------------------------------------------------------------ #
def calculate_ats_score(
    raw_text: str, parsed: ParsedResumeData, jd: ParsedJDData
) -> tuple[float, dict]:
    components: dict[str, float] = {}

    # 1. JD keyword coverage (45 pts) — how much of THIS job description's
    #    vocabulary the resume's skills actually cover. This is what makes
    #    ats_score change when the same resume is scored against a
    #    different JD, instead of staying fixed regardless of JD.
    jd_skills = dedupe_normalized(list(jd.required_skills) + list(jd.preferred_skills))
    if jd_skills:
        matched, _missing = match_skills(parsed.skills, jd_skills)
        components["jd_keyword_coverage"] = round(len(matched) / len(jd_skills) * 45, 2)
    else:
        components["jd_keyword_coverage"] = 45.0

    # 2. Contact completeness (10 pts)
    contact_pts = 0.0
    if parsed.email:
        contact_pts += 6
    if parsed.phone:
        contact_pts += 4
    components["contact_completeness"] = contact_pts

    # 3. Standard section coverage (15 pts)
    lowered = raw_text.lower()
    section_hits = sum(1 for marker in _CORE_SECTION_MARKERS if marker in lowered)
    components["section_coverage"] = round(15 * section_hits / len(_CORE_SECTION_MARKERS), 2)

    # 4. Quantified impact in bullets (15 pts)
    bullets = [b for item in parsed.work_history for b in item.bullets]
    if bullets:
        quantified = sum(1 for b in bullets if _METRIC_RE.search(b))
        components["quantified_impact"] = round(quantified / len(bullets) * 15, 2)
    else:
        components["quantified_impact"] = 0.0

    # 5. Resume length / word count sanity (10 pts) — ATS systems penalize
    #    resumes that are too sparse (under-parsed) or excessively long.
    word_count = len(raw_text.split())
    if 250 <= word_count <= 1100:
        components["length_check"] = 10.0
    elif 120 <= word_count < 250 or 1100 < word_count <= 1600:
        components["length_check"] = 6.0
    else:
        components["length_check"] = 2.0

    # 6. Work history structure present (5 pts)
    components["work_history_structure"] = 5.0 if parsed.work_history else 0.0

    total = round(sum(components.values()), 2)
    return min(total, 100.0), components


# ------------------------------------------------------------------------ #
# match_score: fit against a specific JD
# ------------------------------------------------------------------------ #
def calculate_match_score(
    resume: ParsedResumeData, jd: ParsedJDData
) -> tuple[float, list[str], list[str], dict]:
    all_jd_skills = jd.required_skills + jd.preferred_skills
    matched, missing = match_skills(resume.skills, all_jd_skills)

    required_matched, required_missing = match_skills(resume.skills, jd.required_skills)
    preferred_matched, _ = match_skills(resume.skills, jd.preferred_skills)

    required_ratio = (
        len(required_matched) / len(jd.required_skills) if jd.required_skills else 1.0
    )
    preferred_ratio = (
        len(preferred_matched) / len(jd.preferred_skills) if jd.preferred_skills else 1.0
    )

    # required skills weigh more heavily than preferred ones
    skill_component = required_ratio * 65 + preferred_ratio * 15

    if jd.min_experience_years > 0:
        exp_ratio = min(resume.experience_years / jd.min_experience_years, 1.0)
    else:
        exp_ratio = 1.0
    experience_component = exp_ratio * 20

    total = round(skill_component + experience_component, 2)
    components = {
        "required_skill_match_pct": round(required_ratio * 100, 1),
        "preferred_skill_match_pct": round(preferred_ratio * 100, 1),
        "experience_match_pct": round(exp_ratio * 100, 1),
    }
    return min(total, 100.0), matched, missing, components


# ------------------------------------------------------------------------ #
# Explainable improvement suggestions (ISSUE-16)
# ------------------------------------------------------------------------ #
def generate_suggestions(
    resume: ParsedResumeData,
    jd: ParsedJDData,
    missing_skills: list[str],
    ats_components: dict,
) -> list[ImprovementSuggestion]:
    suggestions: list[ImprovementSuggestion] = []

    if missing_skills:
        core_missing = [s for s in missing_skills if s in jd.required_skills]
        if core_missing:
            suggestions.append(
                ImprovementSuggestion(
                    category="Formatting & Keywords",
                    action=(
                        "Add evidence of these required keywords the JD looks for: "
                        + ", ".join(core_missing[:5]) + "."
                    ),
                    impact="High",
                )
            )
        nice_to_have = [s for s in missing_skills if s not in core_missing]
        if nice_to_have:
            suggestions.append(
                ImprovementSuggestion(
                    category="Formatting & Keywords",
                    action=(
                        "Consider mentioning these preferred skills if you have exposure: "
                        + ", ".join(nice_to_have[:5]) + "."
                    ),
                    impact="Medium",
                )
            )

    if ats_components.get("quantified_impact", 15) < 7.5:
        suggestions.append(
            ImprovementSuggestion(
                category="Experience Detail",
                action="Quantify outcomes in your work history bullets using numbers or "
                       "percentage metrics (e.g. 'reduced latency by 30%').",
                impact="Medium",
            )
        )

    if ats_components.get("contact_completeness", 10) < 10:
        suggestions.append(
            ImprovementSuggestion(
                category="Contact Information",
                action="Ensure both an email address and a phone number are clearly listed "
                       "near the top of the resume.",
                impact="High",
            )
        )

    if ats_components.get("section_coverage", 15) < 15:
        suggestions.append(
            ImprovementSuggestion(
                category="Structure",
                action="Use standard, clearly labeled section headers "
                       "(Experience, Education, Skills) so ATS parsers can locate content.",
                impact="Medium",
            )
        )

    if jd.min_experience_years and resume.experience_years < jd.min_experience_years:
        gap = round(jd.min_experience_years - resume.experience_years, 1)
        suggestions.append(
            ImprovementSuggestion(
                category="Experience Detail",
                action=(
                    f"This role asks for {jd.min_experience_years}+ years of experience; "
                    f"you are ~{gap} years short. Emphasize transferable projects or "
                    "freelance/academic work that closes the gap."
                ),
                impact="Medium",
            )
        )

    if not resume.work_history:
        suggestions.append(
            ImprovementSuggestion(
                category="Structure",
                action="Add a structured work history section with company, role, "
                       "dates, and bullet-point achievements.",
                impact="High",
            )
        )

    if not suggestions:
        suggestions.append(
            ImprovementSuggestion(
                category="Overall",
                action="Strong match — resume already covers the key JD requirements. "
                       "Consider tailoring bullet order to mirror the JD's priorities.",
                impact="Low",
            )
        )

    return suggestions
