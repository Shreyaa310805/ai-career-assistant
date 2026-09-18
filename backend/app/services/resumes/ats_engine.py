"""
ISSUE-14 — ATS scoring engine.
ISSUE-16 — Explainable screening report (improvement suggestions).

`ats_score` measures resume *quality/parseability against industry-standard
formatting* (structure, quantified impact, contact completeness) blended with
how well the resume's content overlaps the given JD — so it genuinely moves
when either the resume or the JD changes. `match_score` measures *fit against
a specific JD* in more detail (required vs. preferred skill overlap +
experience match). Both land in ats_reports per the fixed DB schema.

The JD-alignment component (`skills_listed`) deliberately does not rely
solely on structured skill extraction: many real job postings are written as
prose with no bulleted "Requirements" section, which leaves
`ParsedJDData.required_skills`/`preferred_skills` empty and would silently
make the score JD-independent again. `_keyword_overlap_ratio()` is a plain
significant-word overlap between the resume and the raw JD text, so there is
always a signal that responds to the JD's actual wording, blended with the
structured skill match when one is available.

Every score is computed from named, inspectable sub-components so the
"explainable" requirement is met: `explain()` returns the component
breakdown, and `generate_suggestions()` turns the same signals into
concrete, actionable feedback.
"""
import re

from app.schemas.resume import ImprovementSuggestion, ParsedJDData, ParsedResumeData
from app.services.resumes.matching import match_skills, skill_overlap_ratio

_BULLET_RE = re.compile(r"^[\s]*[-*•●▪]\s+")
_METRIC_RE = re.compile(r"\d")
_CORE_SECTION_MARKERS = ("experience", "education", "skill")

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]{1,}")
# Generic filler words, not skill/role signal — excluded so overlap reflects
# actual content words rather than shared grammar.
_STOPWORDS = frozenset({
    "the", "and", "a", "an", "to", "of", "in", "for", "on", "with", "is", "are",
    "as", "at", "by", "or", "this", "that", "will", "be", "have", "has", "had",
    "you", "your", "we", "our", "us", "they", "their", "it", "its", "from",
    "into", "about", "other", "such", "can", "may", "new", "all", "any", "one",
    "two", "per", "up", "out", "if", "so", "but", "than", "then", "there",
    "here", "more", "most", "some", "each", "who", "what", "when", "where",
    "which", "not", "also", "etc", "including", "include", "includes",
    "looking", "role", "job", "team", "years", "year", "experience",
    "required", "preferred", "must", "should", "would", "strong",
    "excellent", "using", "work", "working", "across", "ability", "able",
})


def _significant_words(text: str) -> set[str]:
    return {
        match.group(0).lower()
        for match in _WORD_RE.finditer(text)
        if len(match.group(0)) > 2 and match.group(0).lower() not in _STOPWORDS
    }


def _keyword_overlap_ratio(resume_text: str, jd_text: str) -> float:
    """Fraction of the JD's significant words also present in the resume.

    Independent of the skills taxonomy, so it always reflects the JD's
    actual wording even when structured skill extraction comes back empty.
    """
    jd_words = _significant_words(jd_text)
    if not jd_words:
        return 1.0
    resume_words = _significant_words(resume_text)
    return len(jd_words & resume_words) / len(jd_words)


# ------------------------------------------------------------------------ #
# ats_score: resume quality independent of any JD
# ------------------------------------------------------------------------ #
def calculate_ats_score(
    raw_text: str,
    parsed: ParsedResumeData,
    jd: ParsedJDData | None = None,
    jd_text: str = "",
) -> tuple[float, dict]:
    components: dict[str, float] = {}

    # 1. Contact completeness (15 pts)
    contact_pts = 0.0
    if parsed.email:
        contact_pts += 8
    if parsed.phone:
        contact_pts += 7
    components["contact_completeness"] = contact_pts

    # 2. Standard section coverage (20 pts)
    lowered = raw_text.lower()
    section_hits = sum(1 for marker in _CORE_SECTION_MARKERS if marker in lowered)
    components["section_coverage"] = round(20 * section_hits / len(_CORE_SECTION_MARKERS), 2)

    # 3. JD alignment (15 pts) — blends structured skill overlap (matched
    #    required/preferred skills) with a plain keyword overlap against the
    #    raw JD text. The keyword signal is what keeps this responsive even
    #    when a prose-style JD yields no extractable skill list. Falls back
    #    to a plain resume skill count when no JD is available at all.
    jd_skills = [*jd.required_skills, *jd.preferred_skills] if jd else []
    ratios = []
    if jd_skills:
        ratios.append(skill_overlap_ratio(parsed.skills, jd_skills))
    if jd_text.strip():
        ratios.append(_keyword_overlap_ratio(raw_text, jd_text))
    if ratios:
        components["skills_listed"] = round(sum(ratios) / len(ratios) * 15, 2)
    else:
        components["skills_listed"] = round(min(len(parsed.skills), 8) / 8 * 15, 2)

    # 4. Quantified impact in bullets (20 pts)
    bullets = [b for item in parsed.work_history for b in item.bullets]
    if bullets:
        quantified = sum(1 for b in bullets if _METRIC_RE.search(b))
        components["quantified_impact"] = round(quantified / len(bullets) * 20, 2)
    else:
        components["quantified_impact"] = 0.0

    # 5. Resume length / word count sanity (15 pts) — ATS systems penalize
    #    resumes that are too sparse (under-parsed) or excessively long.
    word_count = len(raw_text.split())
    if 250 <= word_count <= 1100:
        components["length_check"] = 15.0
    elif 120 <= word_count < 250 or 1100 < word_count <= 1600:
        components["length_check"] = 9.0
    else:
        components["length_check"] = 3.0

    # 6. Work history structure present (15 pts)
    components["work_history_structure"] = 15.0 if parsed.work_history else 0.0

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

    if ats_components.get("quantified_impact", 20) < 10:
        suggestions.append(
            ImprovementSuggestion(
                category="Experience Detail",
                action="Quantify outcomes in your work history bullets using numbers or "
                       "percentage metrics (e.g. 'reduced latency by 30%').",
                impact="Medium",
            )
        )

    if ats_components.get("contact_completeness", 15) < 15:
        suggestions.append(
            ImprovementSuggestion(
                category="Contact Information",
                action="Ensure both an email address and a phone number are clearly listed "
                       "near the top of the resume.",
                impact="High",
            )
        )

    if ats_components.get("section_coverage", 20) < 20:
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


# ------------------------------------------------------------------------ #
# Contextual explanations of the ATS score
# ------------------------------------------------------------------------ #
_SECTION_NAMES = {"experience": "Experience", "education": "Education", "skill": "Skills"}

_ATS_MAX_POINTS: dict[str, float] = {
    "contact_completeness": 15,
    "section_coverage": 20,
    "skills_listed": 15,
    "quantified_impact": 20,
    "length_check": 15,
    "work_history_structure": 15,
}

_ATS_LABELS: dict[str, str] = {
    "contact_completeness": "contact details",
    "section_coverage": "section coverage",
    "skills_listed": "skills alignment",
    "quantified_impact": "quantified impact",
    "length_check": "resume length",
    "work_history_structure": "work history",
}


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def explain_ats_components(
    raw_text: str,
    parsed: ParsedResumeData,
    components: dict[str, float],
    jd: ParsedJDData | None = None,
    jd_text: str = "",
) -> dict[str, str]:
    """One sentence per ATS component, derived from this resume's own data.

    Mirrors the checks in `calculate_ats_score()`, so every statement (e.g.
    "3 of 5 bullets include a metric") is the same fact the score used.
    """
    explanations: dict[str, str] = {}

    # Contact details: say which piece is missing rather than a generic note.
    if parsed.email and parsed.phone:
        explanations["contact_completeness"] = "Both an email address and a phone number were found."
    elif parsed.email:
        explanations["contact_completeness"] = (
            "Email found, but no phone number was detected — add one near the top."
        )
    elif parsed.phone:
        explanations["contact_completeness"] = (
            "Phone number found, but no email address was detected — add one near the top."
        )
    else:
        explanations["contact_completeness"] = (
            "Neither an email address nor a phone number was detected."
        )

    lowered = raw_text.lower()
    found = [m for m in _CORE_SECTION_MARKERS if m in lowered]
    absent = [_SECTION_NAMES[m] for m in _CORE_SECTION_MARKERS if m not in lowered]
    if not absent:
        explanations["section_coverage"] = (
            "All 3 core sections (Experience, Education, Skills) were detected."
        )
    else:
        explanations["section_coverage"] = (
            f"{len(found)} of {len(_CORE_SECTION_MARKERS)} core sections detected; "
            f"no {', '.join(absent)} heading was found."
        )

    jd_skills = [*jd.required_skills, *jd.preferred_skills] if jd else []
    if jd_skills:
        matched, _ = match_skills(parsed.skills, jd_skills)
        explanations["skills_listed"] = (
            f"{len(matched)} of {_plural(len(jd_skills), 'skill')} in the job description "
            "appear on your resume."
        )
    elif jd_text.strip():
        pct = round(_keyword_overlap_ratio(raw_text, jd_text) * 100)
        explanations["skills_listed"] = (
            f"About {pct}% of the job description's key terms also appear on your resume."
        )
    else:
        explanations["skills_listed"] = (
            f"{_plural(len(parsed.skills), 'skill')} listed; 8 or more earns full points "
            "when no job description is given."
        )

    bullets = [b for item in parsed.work_history for b in item.bullets]
    if not bullets:
        explanations["quantified_impact"] = (
            "No bullet points were found under your work history, so nothing could be checked for metrics."
        )
    else:
        quantified = sum(1 for b in bullets if _METRIC_RE.search(b))
        explanations["quantified_impact"] = (
            f"{quantified} of {_plural(len(bullets), 'bullet')} include a metric or number."
        )

    word_count = len(raw_text.split())
    if 250 <= word_count <= 1100:
        explanations["length_check"] = (
            f"{word_count} words — within the 250–1100 range ATS parsers handle best."
        )
    elif word_count < 250:
        explanations["length_check"] = (
            f"{word_count} words — on the short side; aim for at least 250."
        )
    else:
        explanations["length_check"] = (
            f"{word_count} words — longer than the 1100 that parses cleanly; trim it."
        )

    if parsed.work_history:
        explanations["work_history_structure"] = (
            f"{_plural(len(parsed.work_history), 'role')} detected with company and title."
        )
    else:
        explanations["work_history_structure"] = (
            "No structured work history (company, role, dates) could be parsed."
        )

    return {key: text for key, text in explanations.items() if key in components}


def summarize_ats_score(components: dict[str, float]) -> str:
    """Headline for the score: the strongest check and where points leak most.

    Ranks by fraction of available points earned, so a 15-point check and a
    20-point check are compared fairly; the leak is the largest absolute loss.
    """
    known = {k: v for k, v in components.items() if k in _ATS_MAX_POINTS}
    if not known:
        return ""

    ratio = {k: v / _ATS_MAX_POINTS[k] for k, v in known.items()}
    lost = {k: _ATS_MAX_POINTS[k] - v for k, v in known.items()}

    strongest = max(ratio, key=lambda k: (ratio[k], _ATS_MAX_POINTS[k]))
    weakest = max(lost, key=lambda k: lost[k])

    strong_text = (
        f"Your strongest area is {_ATS_LABELS[strongest]} "
        f"({round(known[strongest])}/{_ATS_MAX_POINTS[strongest]:g} points)."
    )
    if lost[weakest] < 1:
        return f"{strong_text} Every check is at or near full marks."
    return (
        f"{strong_text} Most points are being lost on {_ATS_LABELS[weakest]}, "
        f"which earned {round(known[weakest])} of {_ATS_MAX_POINTS[weakest]:g}."
    )
