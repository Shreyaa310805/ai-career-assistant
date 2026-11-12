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

Requirements worded as alternatives ("Python, Java or JavaScript") are
grouped from the JD's own text and scored as a single requirement that any
one of the alternatives satisfies — see `matching.requirement_units()`. Both
scores are pure functions of (resume text, parsed data, JD), so the same
resume and JD always produce the same numbers.

Every score is computed from named, inspectable sub-components so the
"explainable" requirement is met: `explain()` returns the component
breakdown, and `generate_suggestions()` turns the same signals into
concrete, actionable feedback.
"""
import re
from dataclasses import dataclass

from app.schemas.resume import ImprovementSuggestion, ParsedJDData, ParsedResumeData
from app.services.resumes.matching import (
    Requirement,
    evaluate_requirements,
    match_skills,
    requirement_match_ratio,
    requirement_units,
)

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
# Quantified impact
#
# Achievement statements are read straight from the resume text, not only
# from the parser's `work_history[].bullets`: PDF extraction often drops the
# bullet glyphs, wraps one bullet over several lines, and Projects /
# Achievements sections never reach `work_history` at all — which left the
# check at 0 for resumes that plainly contain numbers. The parsed bullets are
# only used when the text has no recognisable achievement section.
#
# A statement counts as quantified when it still contains a number after
# dates, years and version-style names (Python3, EC2, GPT-4) are removed, or
# uses an explicit magnitude word ("doubled", "percent"). Dates are stripped
# because "Jan 2024 – Present" says nothing about impact.
# ------------------------------------------------------------------------ #
QUANTIFIED_IMPACT_MAX = 20.0
# Share of achievement statements that must carry a metric for full points.
# Not every bullet can sensibly hold a number, so half earns the maximum.
QUANTIFIED_TARGET_SHARE = 0.5

_BULLET_MARKER_RE = re.compile(r"^\s*(?:[-*•●▪◦‣⁃➢➤►▶✓✔■□○◆◇~]|o(?=\s)|\d{1,2}[.)](?=\s))\s*")
_ACHIEVEMENT_HEADERS = (
    "experience", "employment", "work history", "internship", "project",
    "achievement", "accomplishment", "award", "leadership", "volunteer",
    "research", "responsibilit", "career history", "positions",
)
_OTHER_HEADERS = (
    "education", "skill", "summary", "objective", "profile", "about me",
    "certification", "certificate", "course", "contact", "language", "interest",
    "hobbies", "reference", "personal", "declaration", "publication", "tools",
    "technologies",
)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_RE = re.compile(
    rf"\b{_MONTHS}\s*[',]?\s*(?:19|20)?\d{{2}}\b"      # Jan 2024, Sept '23
    r"|\b\d{1,2}\s*/\s*(?:19|20)\d{2}\b"               # 06/2024
    r"|\b(?:19|20)\d{2}\s*[-–—/]\s*(?:\d{2,4})\b"       # 2022-2024, 2021/22
    r"|\b(?:19|20)\d{2}\b",                              # lone years
    re.IGNORECASE,
)
# Digits glued to letters are names, not measurements: Python3, EC2, GPT-4, HTML5.
_VERSIONED_NAME_RE = re.compile(r"\b[A-Za-z]+[-.]?\d[\w.]*")
_MAGNITUDE_WORD_RE = re.compile(
    r"\b(?:percent|doubled|tripled|quadrupled|halved|tenfold|twofold|threefold"
    r"|million|billion|thousand|lakh|crore)\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_ALPHA_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _section_kind(line: str) -> str | None:
    """'achievement' / 'other' when the line is a section heading, else None."""
    text = line.strip().rstrip(":").strip()
    if not text or len(text) > 45 or any(ch.isdigit() for ch in text):
        return None
    words = text.split()
    if len(words) > 5:
        return None
    looks_like_heading = text.isupper() or line.strip().endswith(":") or len(words) <= 3
    if not looks_like_heading:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _OTHER_HEADERS):
        return "other"
    if any(marker in lowered for marker in _ACHIEVEMENT_HEADERS):
        return "achievement"
    return None


def _has_date(line: str) -> bool:
    return bool(_DATE_RE.search(line)) or "present" in line.lower()


def achievement_statements(raw_text: str) -> list[str]:
    """Individual achievement statements from Experience/Projects-style sections.

    Wrapped lines are re-joined; a new statement starts at a bullet marker,
    at a dated entry line, or after a line that ends a sentence. Title-only
    lines ("Software Engineer at Acme") are dropped by the length filter.
    """
    lines = raw_text.splitlines()
    has_sections = any(_section_kind(line) for line in lines)

    chunks: list[tuple[str, bool]] = []  # (text, started with a bullet)
    in_achievements = not has_sections
    current: list[str] = []
    current_bullet = False

    def flush() -> None:
        nonlocal current, current_bullet
        if current:
            chunks.append((" ".join(current), current_bullet))
        current, current_bullet = [], False

    for line in lines:
        kind = _section_kind(line)
        if kind is not None:
            flush()
            in_achievements = kind == "achievement"
            continue
        if not in_achievements or not line.strip():
            flush()
            continue
        bullet = _BULLET_MARKER_RE.match(line)
        if not has_sections and not bullet:
            continue  # no section structure: only explicit bullets are trustworthy
        text = _BULLET_MARKER_RE.sub("", line, count=1).strip() if bullet else line.strip()
        if bullet or _has_date(line) or (current and current[-1].endswith((".", "!", "?"))):
            flush()
            current_bullet = bool(bullet)
        current.append(text)
    flush()

    statements: list[str] = []
    for chunk, from_bullet in chunks:
        for sentence in _SENTENCE_SPLIT_RE.split(chunk):
            sentence = sentence.strip()
            words = len(_ALPHA_WORD_RE.findall(_DATE_RE.sub(" ", sentence)))
            # Bullets may be terse ("Cut costs by 20%"); unmarked lines need
            # sentence length so headings and title lines are not counted.
            if words >= (3 if from_bullet else 6):
                statements.append(sentence)
    return statements


def is_quantified(statement: str) -> bool:
    """True when the statement states a measurable result."""
    cleaned = _VERSIONED_NAME_RE.sub(" ", _DATE_RE.sub(" ", statement))
    return bool(re.search(r"\d", cleaned) or _MAGNITUDE_WORD_RE.search(cleaned))


def quantified_impact_evidence(raw_text: str, parsed: ParsedResumeData) -> tuple[int, int, str]:
    """(quantified statements, total statements, source) behind the score."""
    statements = achievement_statements(raw_text)
    source = "resume text"
    if not statements:
        statements = [b for item in parsed.work_history for b in item.bullets if b.strip()]
        source = "work history bullets"
    return sum(1 for s in statements if is_quantified(s)), len(statements), source


def quantified_impact_points(quantified: int, total: int) -> float:
    """points = 20 × min(1, (quantified / total) / 0.5)."""
    if total == 0:
        return 0.0
    share = quantified / total
    return round(QUANTIFIED_IMPACT_MAX * min(1.0, share / QUANTIFIED_TARGET_SHARE), 2)


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
        ratios.append(requirement_match_ratio(parsed.skills, jd_skills, jd_text))
    if jd_text.strip():
        ratios.append(_keyword_overlap_ratio(raw_text, jd_text))
    if ratios:
        components["skills_listed"] = round(sum(ratios) / len(ratios) * 15, 2)
    else:
        components["skills_listed"] = round(min(len(parsed.skills), 8) / 8 * 15, 2)

    # 4. Quantified impact (20 pts) — share of achievement statements that
    #    carry a metric; see quantified_impact_evidence().
    quantified, statement_count, _ = quantified_impact_evidence(raw_text, parsed)
    components["quantified_impact"] = quantified_impact_points(quantified, statement_count)

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
# Base weights (points out of 100). A tier the JD does not specify (no
# preferred skills, no minimum years) is dropped and the remaining weights are
# scaled back up to 100, so a candidate is neither handed free points nor
# penalised for something the posting never asked for.
MATCH_WEIGHTS: dict[str, float] = {"required": 65.0, "preferred": 15.0, "experience": 20.0}


@dataclass(frozen=True)
class MatchScoreDetails:
    """Everything the role match score is computed from, for tracing it."""

    requirements: list[Requirement]
    ratios: dict[str, float]          # tier -> fraction met (0..1), present tiers only
    weights: dict[str, float]         # tier -> effective weight, sums to 100
    points: dict[str, float]          # tier -> weight × ratio
    candidate_years: float
    required_years: float
    score: float

    def tier(self, name: str) -> list[Requirement]:
        return [r for r in self.requirements if r.tier == name]

    @property
    def matched_skills(self) -> list[str]:
        return [skill for r in self.requirements for skill in r.satisfied_by]

    @property
    def missing_skills(self) -> list[str]:
        """Unmet requirements in JD order; every alternative of an unmet group
        is listed together, with equal standing."""
        return [skill for r in self.requirements if not r.met for skill in r.skills]

    @property
    def covered_alternatives(self) -> dict[str, list[str]]:
        """Alternatives not on the resume whose requirement is already met by
        another option ("Java" when the JD says "Python or Java" and the
        resume has Python). They cost nothing and rank last as gaps."""
        return {
            skill: list(r.satisfied_by)
            for r in self.requirements
            if r.met
            for skill in r.unmet_alternatives
        }


def match_score_details(
    resume: ParsedResumeData, jd: ParsedJDData, jd_text: str = ""
) -> MatchScoreDetails:
    """role_match = Σ weight_t × met_t / total_t  (+ experience term).

    * A requirement is one JD skill, or one group of interchangeable
      alternatives ("Go, Python or Java"). Each requirement counts 1, so every
      alternative in a group carries equal importance, and holding any one of
      them meets the whole requirement.
    * experience ratio = min(candidate years / required years, 1).
    """
    requirements = evaluate_requirements(
        resume.skills, jd.required_skills, jd.preferred_skills, jd_text
    )
    ratios: dict[str, float] = {}
    for tier in ("required", "preferred"):
        units = [r for r in requirements if r.tier == tier]
        if units:
            ratios[tier] = sum(1 for r in units if r.met) / len(units)
    if jd.min_experience_years > 0:
        ratios["experience"] = min(resume.experience_years / jd.min_experience_years, 1.0)

    base_total = sum(MATCH_WEIGHTS[tier] for tier in ratios)
    weights = {tier: MATCH_WEIGHTS[tier] * 100 / base_total for tier in ratios} if base_total else {}
    points = {tier: round(weights[tier] * ratios[tier], 2) for tier in ratios}
    score = min(round(sum(weights[t] * ratios[t] for t in ratios), 2), 100.0)

    return MatchScoreDetails(
        requirements=requirements,
        ratios=ratios,
        weights=weights,
        points=points,
        candidate_years=resume.experience_years,
        required_years=jd.min_experience_years,
        score=score,
    )


def calculate_match_score(
    resume: ParsedResumeData, jd: ParsedJDData, jd_text: str = ""
) -> tuple[float, list[str], list[str], dict]:
    """(score, matched, missing, components) — see `match_score_details()`.

    `missing` lists the real gaps first, in JD order. Alternatives that are
    already covered by another option are not gaps and are not in `missing`;
    they are reported separately via `covered_alternatives` so the career
    roadmap can rank them last.
    """
    details = match_score_details(resume, jd, jd_text)
    components: dict[str, float] = {}
    for tier, label in (("required", "required_skill"), ("preferred", "preferred_skill")):
        units = details.tier(tier)
        components[f"{label}_match_pct"] = round(details.ratios.get(tier, 0.0) * 100, 1)
        components[f"{tier}_met"] = float(sum(1 for r in units if r.met))
        components[f"{tier}_total"] = float(len(units))
    components["experience_match_pct"] = round(details.ratios.get("experience", 0.0) * 100, 1)
    for tier in MATCH_WEIGHTS:
        components[f"{tier}_weight"] = round(details.weights.get(tier, 0.0), 2)
        components[f"{tier}_points"] = details.points.get(tier, 0.0)
    return details.score, details.matched_skills, details.missing_skills, components


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _describe_requirement(requirement: Requirement) -> str:
    return " / ".join(requirement.skills) if requirement.is_alternative_group else requirement.skills[0]


def explain_match_score(details: MatchScoreDetails) -> dict[str, str]:
    """Plain-English trace of the role match score, one line per term.

    Each line restates the exact numbers used in `match_score_details()`, so
    "how was 72 reached?" is answered by reading these top to bottom.
    """
    lines: dict[str, str] = {}
    if not details.ratios:
        lines["formula"] = (
            "No skills or minimum experience could be extracted from the job description, "
            "so there was nothing to match against."
        )
        lines["total"] = "Role match = 0."
        return lines

    terms = " + ".join(f"{_fmt(details.weights[t])} × {t}" for t in details.ratios)
    lines["formula"] = (
        f"Role match = {terms}, where each term is the fraction met. Base weights are "
        "65 required / 15 preferred / 20 experience; tiers the job description does not "
        "specify are left out and the rest scaled to 100. A requirement written as "
        "alternatives (\"Go, Python or Java\") counts once and any one option meets it."
    )

    for tier in ("required", "preferred"):
        if tier not in details.ratios:
            continue
        units = details.tier(tier)
        met = sum(1 for r in units if r.met)
        text = (
            f"{met} of {_plural(len(units), f'{tier} requirement')} met "
            f"({round(details.ratios[tier] * 100)}%) → {_fmt(details.points[tier])} of "
            f"{_fmt(details.weights[tier])} points."
        )
        groups = [r for r in units if r.is_alternative_group]
        for group in groups:
            if group.met:
                text += f" \"{_describe_requirement(group)}\" is met by {', '.join(group.satisfied_by)}."
            else:
                text += (
                    f" \"{_describe_requirement(group)}\" is unmet; each option is equally "
                    "important and any one would meet it."
                )
        lines[tier] = text

    if "experience" in details.ratios:
        lines["experience"] = (
            f"{_fmt(details.candidate_years)} of {_fmt(details.required_years)} required years "
            f"({round(details.ratios['experience'] * 100)}%) → {_fmt(details.points['experience'])} "
            f"of {_fmt(details.weights['experience'])} points."
        )

    lines["total"] = (
        " + ".join(_fmt(details.points[t]) for t in details.ratios)
        + f" = {_fmt(details.score)}."
    )
    return lines


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
        # Counted in requirements, not raw skills, so the sentence matches the
        # score: "Python or Java" is one requirement either skill satisfies.
        units = requirement_units(jd_skills, jd_text)
        matched, _ = match_skills(parsed.skills, jd_skills)
        matched_keys = {skill.lower() for skill in matched}
        met = sum(1 for unit in units if any(skill.lower() in matched_keys for skill in unit))
        explanations["skills_listed"] = (
            f"{met} of {_plural(len(units), 'requirement')} in the job description "
            "are covered by your resume."
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

    quantified, statement_count, _ = quantified_impact_evidence(raw_text, parsed)
    if not statement_count:
        explanations["quantified_impact"] = (
            "No achievement statements were found under Experience, Projects or similar "
            "sections, so nothing could be checked for metrics."
        )
    else:
        pct = round(quantified / statement_count * 100)
        explanations["quantified_impact"] = (
            f"{quantified} of {_plural(statement_count, 'achievement statement')} ({pct}%) "
            "include a measurable result; 50% or more earns full points."
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
