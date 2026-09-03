"""
ISSUE-14 — ATS scoring engine.
ISSUE-16 — Explainable screening report (improvement suggestions).

`ats_score` and `match_score` are BOTH computed against the specific JD
passed to /analyze — this mirrors how real ATS platforms work (they score
a resume against the posting's keywords, not in the abstract), and it's
also what the project workflow calls for: "ATS ANALYSIS + JD <-> RESUME
MATCHING" is one combined step that yields both scores together. Analyzing
the same resume against two different JDs should — and now does — produce
two different ats_scores, because each score is (mostly) driven by how
well the resume's content lines up with *that* JD's keywords, on top of a
smaller, JD-independent formatting/quality component:

  - `ats_score`   = JD keyword coverage (45%) + resume formatting/quality
                     signals (55%): contact info, section headers,
                     quantified bullets, length, work-history structure.
                     Answers: "would an ATS keyword-scan of THIS resume
                     for THIS posting flag it as a good match?"
  - `match_score` = required-vs-preferred skill coverage (80%) + experience
                     match (20%). Answers: "how good a candidate fit is
                     this, holistically, for THIS posting?"

They're intentionally correlated (both depend on the JD) but not
identical — a resume can be nicely formatted with a mediocre keyword hit
rate (low ats_score component, but if experience is strong, decent
match_score), or vice versa.

Every score is computed from named, inspectable sub-components so the
"explainable" requirement is met: the returned component dict doubles as
the report's rationale, and `generate_suggestions()` turns those same
signals into concrete, actionable feedback.
"""
import re

from app.schemas import ImprovementSuggestion, ParsedJDData, ParsedResumeData
from app.services.matching import match_skills
from app.services.taxonomy import dedupe_normalized

_BULLET_RE = re.compile(r"^[\s]*[-*•●▪]\s+")
_METRIC_RE = re.compile(r"\d")
_CORE_SECTION_MARKERS = ("experience", "education", "skill")


# ------------------------------------------------------------------------ #
# ats_score: JD keyword coverage + resume formatting/quality
# ------------------------------------------------------------------------ #
def calculate_ats_score(
    raw_text: str, parsed: ParsedResumeData, jd: ParsedJDData
) -> tuple[float, dict]:
    components: dict[str, float] = {}

    # 1. JD keyword coverage (45 pts) — THE component that makes ats_score
    #    vary from one JD to the next, same as it would on a real ATS.
    jd_skills = dedupe_normalized(jd.required_skills + jd.preferred_skills)
    if jd_skills:
        matched, _ = match_skills(parsed.skills, jd_skills)
        coverage_ratio = len(matched) / len(jd_skills)
    else:
        coverage_ratio = 1.0
    components["jd_keyword_coverage"] = round(coverage_ratio * 45, 2)

    # 2. Contact completeness (10 pts)
    contact_pts = 0.0
    if parsed.email:
        contact_pts += 5.5
    if parsed.phone:
        contact_pts += 4.5
    components["contact_completeness"] = round(contact_pts, 2)

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
