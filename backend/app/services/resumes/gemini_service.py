"""
ISSUE-13 — Structured resume/JD parsing.

GeminiService.parse_resume() / .parse_jd() turn unformatted raw text into
the strongly-typed schemas in app/schemas.py (ParsedResumeData / ParsedJDData).

Design goal (per the "zero blocking dependency" mandate): this module must
work with no Gemini API key at all. So:

  1. If GEMINI_API_KEY is set, call Gemini with response_schema=<Pydantic
     model> for constrained JSON output.
  2. On any failure (no key, network error, quota, malformed response),
     fall back to a deterministic heuristic parser built from regex +
     the shared skills taxonomy. The fallback is good enough for the
     standalone test interface and for CI, and is exercised by the test
     suite so behavior never silently depends on network access.
"""
import json
import logging
import re
from datetime import date

from app.core.config import get_settings
from app.schemas.interview import DifficultyEnum, GeneratedQuestion
from app.schemas.resume import ParsedJDData, ParsedResumeData, WorkHistoryItem
from app.services.resumes.taxonomy import (
    extract_all_skills,
    extract_skills_from_sections,
    extract_skills_from_text,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")
_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s*(?:of)?\s*(?:experience|exp)?", re.IGNORECASE
)
# Work-history date ranges, e.g. "2019 - 2023", "Jan 2021 - Present".
_YEAR_RANGE_RE = re.compile(
    r"(19\d{2}|20\d{2})\s*(?:[-–—]|to)\s*(19\d{2}|20\d{2}|present|current)",
    re.IGNORECASE,
)
_EDU_KEYWORDS = (
    "bachelor", "b.s.", "bs ", "b.tech", "btech", "master", "m.s.", "ms ",
    "m.tech", "mtech", "ph.d", "phd", "mba", "b.a.", "m.a.", "associate degree",
    "diploma", "university", "college",
)
_SECTION_HEADERS = {
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "education": ("education", "academic background"),
    "skills": ("skills", "technical skills", "core competencies"),
}


class GeminiService:
    def __init__(self) -> None:
        self._client = None
        if settings.gemini_enabled:
            try:
                from google import genai  # imported lazily; optional dependency

                self._client = genai.Client(api_key=settings.gemini_api_key)
            except Exception as exc:  # pragma: no cover - only hit w/o package
                logger.warning("Gemini client unavailable, using heuristic parser: %s", exc)
                self._client = None

    @property
    def using_llm(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------ #
    # Resume parsing
    # ------------------------------------------------------------------ #
    def parse_resume(self, raw_text: str) -> ParsedResumeData:
        if self._client is not None:
            try:
                return self._parse_resume_via_gemini(raw_text)
            except Exception as exc:
                logger.warning("Gemini resume parse failed, falling back: %s", exc)
        return heuristic_parse_resume(raw_text)

    def _parse_resume_via_gemini(self, raw_text: str) -> ParsedResumeData:
        from google.genai import types  # local import: optional dependency

        prompt = (
            "Extract structured candidate data from this resume text. "
            "Return ONLY fields defined by the schema. "
            "experience_years should be your best numeric estimate of total "
            "professional experience in years (can be fractional).\n\n"
            f"RESUME TEXT:\n{raw_text}"
        )
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParsedResumeData,
            ),
        )
        data = json.loads(response.text)
        return ParsedResumeData.model_validate(data)

    # ------------------------------------------------------------------ #
    # JD parsing
    # ------------------------------------------------------------------ #
    def parse_jd(self, jd_text: str) -> ParsedJDData:
        if self._client is not None:
            try:
                return self._parse_jd_via_gemini(jd_text)
            except Exception as exc:
                logger.warning("Gemini JD parse failed, falling back: %s", exc)
        return heuristic_parse_jd(jd_text)

    def _parse_jd_via_gemini(self, jd_text: str) -> ParsedJDData:
        from google.genai import types

        prompt = (
            "Extract structured requirements from this job description. "
            "required_skills are must-haves; preferred_skills are nice-to-haves. "
            "min_experience_years is the minimum years of experience requested "
            "(0 if unspecified).\n\n"
            f"JOB DESCRIPTION:\n{jd_text}"
        )
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParsedJDData,
            ),
        )
        data = json.loads(response.text)
        return ParsedJDData.model_validate(data)

    # ------------------------------------------------------------------ #
    # Interview question generation
    # ------------------------------------------------------------------ #
    def generate_interview_question(
        self,
        *,
        role: str,
        job_description: str,
        personality: str,
        difficulty: DifficultyEnum,
        resume_skills: list[str],
        matched_skills: list[str],
        missing_skills: list[str],
        question_number: int,
        previous_questions: list[str],
        resume_evidence: str,
    ) -> GeneratedQuestion:
        """Generate one validated question, with a deterministic offline fallback.

        Only public career data is supplied to the model: no name, contact
        details, raw resume text, or file locator leaves the service boundary.
        """
        if self._client is not None:
            try:
                generated = self._generate_interview_question_via_gemini(
                    role=role, job_description=job_description, personality=personality,
                    difficulty=difficulty, resume_skills=resume_skills,
                    matched_skills=matched_skills, missing_skills=missing_skills,
                    question_number=question_number, previous_questions=previous_questions,
                    resume_evidence=resume_evidence,
                )
                if generated.question.strip() in {question.strip() for question in previous_questions}:
                    raise ValueError("Gemini returned a duplicate interview question")
                return generated
            except Exception as exc:
                logger.warning("Gemini interview generation failed, using fallback: %s", exc)
        return heuristic_interview_question(
            role=role, personality=personality, difficulty=difficulty,
            resume_skills=resume_skills, matched_skills=matched_skills,
            missing_skills=missing_skills, question_number=question_number,
            previous_questions=previous_questions,
            resume_evidence=resume_evidence,
        )

    def _generate_interview_question_via_gemini(self, **context) -> GeneratedQuestion:
        from google.genai import types

        prompt = self._interview_question_prompt(**context)
        response = self._client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=GeneratedQuestion,
            ),
        )
        return GeneratedQuestion.model_validate(json.loads(response.text))

    @staticmethod
    def _interview_question_prompt(**context) -> str:
        return (
            "You are interviewing a real candidate for the target role. Create exactly one specific, "
            "natural interview question. Prioritize concrete candidate projects and experience from the "
            "resume evidence, then job requirements/responsibilities, then matched and missing skills. "
            "Probe understanding, implementation, debugging, design, trade-offs, edge cases, or decision "
            "making as appropriate. Do not simply place one skill into a generic template. Vary the question "
            "dimension from previous questions. Skills are context, not mandatory words to insert. "
            "Personality determines the question intent: technical = implementation/design/debugging; friendly = "
            "approachable project or technical discussion; strict = challenging technical reasoning; behavioral = "
            "past experience, ownership, collaboration, decisions, failures, or outcomes (never a hypothetical "
            "implementation/design question); mixed may combine technical and behavioral intent. "
            "Choose a genuinely different interview angle from previous questions whenever possible. Do not "
            "treat the job title as a skill. Do not mention internal generation concepts, considerations, scoring, "
            "strategy names, or reasoning. Never append an instruction to give a different approach or example. "
            "Do not request or include personal/contact information.\n\n"
            f"ROLE: {context['role']}\nJOB DESCRIPTION: {context['job_description'][:12000]}\n"
            f"PERSONALITY: {context['personality']}\nDIFFICULTY: {context['difficulty'].value}\n"
            f"QUESTION NUMBER: {context['question_number']}\nRESUME SKILLS: {context['resume_skills']}\n"
            f"RESUME EVIDENCE (projects, experience, education):\n{context['resume_evidence'][:12000]}\n"
            f"MATCHED SKILLS: {context['matched_skills']}\nMISSING SKILLS: {context['missing_skills']}\n"
            f"PREVIOUS QUESTIONS: {context['previous_questions']}\n\n"
            "Generate exactly one natural question and the existing structured metadata. Do not repeat or merely "
            "rephrase previous questions. Maintain the selected personality and difficulty while staying relevant "
            "to the role, JD, resume, and ATS context."
        )


# ---------------------------------------------------------------------- #
# Heuristic fallback parsers (no external calls; deterministic; tested)
# ---------------------------------------------------------------------- #
def heuristic_parse_resume(raw_text: str) -> ParsedResumeData:
    email_match = _EMAIL_RE.search(raw_text)
    phone_match = _PHONE_RE.search(raw_text)
    skills = extract_all_skills(raw_text)
    experience_years = _estimate_experience_years(raw_text)
    if experience_years == 0.0:
        # No explicit "N years of experience" statement — derive a total
        # from the work-history date ranges instead of scoring it as zero.
        experience_years = _estimate_experience_from_dates(raw_text)
    education = _extract_education(raw_text)
    work_history = _extract_work_history(raw_text)
    candidate_name = _guess_candidate_name(raw_text)

    return ParsedResumeData(
        candidate_name=candidate_name,
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0).strip() if phone_match else "",
        skills=skills,
        experience_years=experience_years,
        work_history=work_history,
        education=education,
    )


def heuristic_interview_question(
    *, role: str, personality: str, difficulty: DifficultyEnum, resume_skills: list[str],
    matched_skills: list[str], missing_skills: list[str], question_number: int,
    previous_questions: list[str], resume_evidence: str,
) -> GeneratedQuestion:
    """Stable, context-driven fallback used when Gemini is unavailable."""
    skills = missing_skills or matched_skills or resume_skills
    topic = skills[(question_number - 1) % len(skills)] if skills else ""
    question_topic = _natural_topic(topic)
    project = _resume_project_evidence(resume_evidence, previous_questions, question_number)
    if personality == "behavioral" and project:
        project_title = project.split(" — ", 1)[0].split(" - ", 1)[0].strip()
        strategies = {
            "challenge": f"Tell me about a difficult challenge you faced while building {project_title}. How did you approach it and what was the outcome?",
            "decision": f"Describe an important decision you made in {project_title}. What alternatives did you consider, and why did you choose that approach?",
            "failure": f"Tell me about a setback or mistake you encountered in {project_title}. How did you communicate it and what did you learn?",
            "collaboration": f"How did you work with others or gather feedback while building {project_title}? What did that change?",
            "ownership": f"What part of {project_title} did you take ownership of, and how did you ensure it was completed well?",
            "learning": f"What did building {project_title} teach you that changed how you approach later work?",
        }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "behavioral"
    elif project:
        project_title = project.split(" — ", 1)[0].split(" - ", 1)[0].strip()
        if personality == "friendly":
            strategies = {
                "walkthrough": f"I would love to hear about {project_title}. Could you walk me through what it does and your role in building it?",
                "learning": f"What did you enjoy learning while building {project_title}, and how did you apply it?",
                "challenge": f"Could you walk me through an interesting challenge in {project_title} and how you worked through it?",
                "improvement": f"If you had more time with {project_title}, what practical improvement would you make first?",
                "reasoning": f"What guided your approach to {project_title} when you had to choose between possible solutions?",
            }
        elif personality == "strict":
            strategies = {
                "trade_off": f"Defend the key design decisions in {project_title}. What trade-offs and failure modes did you account for?",
                "production_risk": f"Where would {project_title} break under production load? Give a concrete diagnosis and remediation plan.",
                "edge_case": f"What edge case in {project_title} is most likely to produce incorrect behavior, and how would you address it?",
                "debugging": f"A critical workflow in {project_title} is failing intermittently. How would you isolate the root cause?",
                "scalability": f"What would be the first bottleneck if {project_title} had ten times the traffic, and why?",
            }
        elif personality == "mixed":
            strategies = {
                "architecture": f"In your {project_title}, how did you structure the implementation{f' around {question_topic}' if question_topic else ''}?",
                "challenge": f"Tell me about a difficult challenge you faced while building {project_title}. How did you respond?",
                "debugging": f"Walk me through a difficult bug or edge case in {project_title}. How did you diagnose and fix it?",
                "decision": f"Describe a design decision you made in {project_title}. What alternatives did you consider?",
                "scalability": f"If {project_title} had to support substantially more users, what would you change first and why?",
            }
        else:
            implementation_focus = f" around {question_topic}" if question_topic else ""
            strategies = {
                "architecture": f"In your {project_title}, how did you structure the implementation{implementation_focus}? What trade-off did you make?",
                "debugging": f"Walk me through a difficult bug or edge case in {project_title}. How did you diagnose and fix it?",
                "scalability": f"If {project_title} had to support substantially more users, what would you change first and why?",
                "design_decision": f"What design decision in {project_title} would you revisit today, and what impact would that have?",
                "testing": f"How did you test {project_title}, and which failure scenario were you most concerned about?",
                "security": f"What security or data-protection risk did you consider in {project_title}, and how did you mitigate it?",
            }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "project_deep_dive"
    elif personality == "behavioral":
        strategies = {
            "challenge": f"Tell me about a challenge you faced in a project or work experience relevant to the {role or 'target'} role. How did you approach it and what was the outcome?",
            "decision": "Tell me about an important decision you made with incomplete information. What alternatives did you consider?",
            "failure": "Tell me about a mistake or setback in a project. How did you respond and what did you learn?",
            "collaboration": "Describe a time you had to align with someone who had a different technical perspective. How did you handle it?",
            "learning": "Tell me about a time feedback changed how you approached a project or task.",
        }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "behavioral"
    elif personality == "friendly":
        strategies = {
            "walkthrough": f"Let us talk through how you would approach a {role or 'target'} project. What would you try first, and why?",
            "learning": "What is a technical concept you recently learned through a project, and what helped it click for you?",
            "challenge": "What is a project challenge you found satisfying to solve, and how did you work through it?",
            "improvement": "Think of a project you completed. What practical improvement would you make if you revisited it?",
            "reasoning": "When you have several possible ways to solve a problem, how do you decide where to start?",
        }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "scenario"
    elif personality == "strict":
        strategies = {
            "failure_mode": f"Design a production-ready approach for a {role or 'target'} role. Which failure mode would you test first, and why?",
            "edge_case": f"What edge case would most likely break a {role or 'target'} feature, and how would you detect it?",
            "debugging": f"A {role or 'target'} feature fails only under load. What evidence would you gather before changing code?",
            "trade_off": f"Defend a technical trade-off you would make when building a {role or 'target'} system.",
            "reliability": f"What reliability risk would you address before releasing a {role or 'target'} feature?",
        }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "design"
    else:
        if question_topic:
            strategies = {
                "implementation": f"How would you implement {question_topic} for a realistic {role or 'target'} problem? Explain the key components.",
                "debugging": f"A {role or 'target'} feature related to {question_topic} is failing intermittently. How would you investigate it?",
                "trade_off": f"What trade-offs would you evaluate when choosing an approach involving {question_topic} for a {role or 'target'} system?",
                "edge_case": f"What edge cases would you test first when building a {role or 'target'} feature involving {question_topic}?",
                "testing": f"How would you test a {role or 'target'} feature built with {question_topic} before release?",
            }
        else:
            strategies = {
                "implementation": f"How would you break down a realistic {role or 'target'} problem into implementable components?",
                "debugging": f"A {role or 'target'} feature is failing intermittently. How would you investigate it?",
                "trade_off": f"What trade-offs would you evaluate before choosing an approach for a {role or 'target'} system?",
                "edge_case": f"What edge cases would you test first when building a {role or 'target'} feature?",
                "testing": f"How would you validate a {role or 'target'} feature before release?",
            }
        question, _ = _question_for_new_angle(strategies, previous_questions, question_number)
        question_type = "technical" if personality == "technical" else "mixed"
    return GeneratedQuestion(
        question=question, topic=topic, question_type=question_type, difficulty=difficulty,
        expected_skills=[topic] if topic else [],
        reason=f"Targets {project_title if project else (topic or role)} using the candidate's resume and role context.",
    )


def _resume_project_evidence(
    resume_evidence: str, previous_questions: list[str], question_number: int,
) -> str:
    """Choose a less-covered project without changing question-angle selection."""
    in_projects = False
    candidates: list[str] = []
    for raw_line in resume_evidence.splitlines():
        line = raw_line.strip(" \t-•*")
        if not line:
            continue
        if line.lower() in {"projects", "personal projects", "academic projects", "project experience"}:
            in_projects = True
            continue
        if in_projects and line.lower() in {
            "experience", "work experience", "professional experience", "education", "skills",
            "certifications", "achievements",
        }:
            break
        if in_projects and len(line) > 8 and (
            not candidates or any(separator in line for separator in (" — ", " - ", "|", ":"))
        ):
            candidates.append(line[:400])
    if not candidates:
        return ""

    history = " ".join(previous_questions).lower()
    # Relevance comes from the resume/JD context already supplied to Gemini;
    # this fallback only avoids letting the first parsed project monopolize a
    # sequence. Question number breaks ties among equally uncovered evidence.
    coverage = [history.count(candidate.split(" — ", 1)[0].split(" - ", 1)[0].strip().lower()) for candidate in candidates]
    least_covered = min(coverage)
    options = [candidate for candidate, count in zip(candidates, coverage) if count == least_covered]
    return options[(question_number - 1) % len(options)]


_ANGLE_HINTS: dict[str, tuple[str, ...]] = {
    "architecture": ("structure the implementation", "key components"),
    "implementation": ("implement", "break down"),
    "debugging": ("bug", "failing", "root cause", "investigate"),
    "scalability": ("more users", "traffic", "bottleneck", "under load"),
    "trade_off": ("trade-off", "tradeoff"),
    "edge_case": ("edge case", "incorrect behavior"),
    "testing": ("test ", "validate"),
    "security": ("security", "data-protection"),
    "design_decision": ("design decision",),
    "challenge": ("challenge",),
    "decision": ("important decision", "alternatives did you consider"),
    "failure": ("setback", "mistake"),
    "collaboration": ("work with others", "different technical perspective"),
    "ownership": ("ownership",),
    "learning": ("what did", "feedback changed", "recently learned"),
    "walkthrough": ("walk me through", "what it does"),
    "improvement": ("improvement", "revisited"),
    "reasoning": ("guided your approach", "decide where to start"),
    "production_risk": ("production load", "production-ready"),
    "failure_mode": ("failure mode",),
    "reliability": ("reliability",),
}


def _question_for_new_angle(
    strategies: dict[str, str], previous_questions: list[str], question_number: int,
) -> tuple[str, str]:
    """Choose an unused interview intent before producing its natural wording."""
    used_angles = _used_question_angles(previous_questions)
    options = list(strategies.items())
    start = (question_number - 1) % len(options)
    rotated = options[start:] + options[:start]
    for angle, question in rotated:
        if angle not in used_angles and question.strip() not in {item.strip() for item in previous_questions}:
            return question, angle
    for angle, question in rotated:
        if question.strip() not in {item.strip() for item in previous_questions}:
            return question, angle
    # All local fallback angles were exhausted. This preserves a natural
    # question rather than fabricating a uniqueness suffix.
    return rotated[0][1], rotated[0][0]


def _used_question_angles(previous_questions: list[str]) -> set[str]:
    used: set[str] = set()
    for question in previous_questions:
        lowered = question.lower()
        for angle, hints in _ANGLE_HINTS.items():
            if any(hint in lowered for hint in hints):
                used.add(angle)
    return used


def _natural_topic(topic: str) -> str:
    """Avoid leaking parser labels such as 'Understanding of X' into speech."""
    normalized = re.sub(r"^understanding of\s+", "", topic, flags=re.IGNORECASE).strip()
    if normalized.lower() in {"communication skills", "leadership", "teamwork", "problem solving"}:
        return ""
    return normalized


# Headers under which a listed skill is a nice-to-have rather than a must-have.
_PREFERRED_HEADER_RE = re.compile(
    r"^\s*(?:[-•*]\s*)?(preferred qualifications|preferred skills|nice to have"
    r"|bonus points|good to have|preferred|bonus)\s*:?\s*$",
    re.IGNORECASE,
)
_PREFERRED_INLINE_MARKERS = ("nice to have", "preferred", "bonus", "a plus", "good to have")


def _split_preferred_block(jd_text: str) -> tuple[str, str]:
    """Split a JD into (must-have text, nice-to-have text) on the first
    preferred-qualifications header. Returns ("", "") when no such header
    exists, so callers know to fall back to the inline-marker heuristic."""
    lines = jd_text.split("\n")
    for index, line in enumerate(lines):
        if _PREFERRED_HEADER_RE.match(line):
            return "\n".join(lines[:index]), "\n".join(lines[index:])
    return "", ""


def heuristic_parse_jd(jd_text: str) -> ParsedJDData:
    min_years = _estimate_experience_years(jd_text)

    required_text, preferred_text = _split_preferred_block(jd_text)
    if preferred_text:
        # The JD labels its own sections — trust that over proximity guessing.
        required = extract_all_skills(required_text)
        preferred_all = extract_all_skills(preferred_text)
        required_lower = {s.lower() for s in required}
        preferred = [s for s in preferred_all if s.lower() not in required_lower]
    else:
        required, preferred = _bucket_by_inline_markers(jd_text)

    role_title = _guess_role_title(jd_text)
    responsibilities = _extract_bullets(jd_text)[:8]

    return ParsedJDData(
        role_title=role_title,
        required_skills=required,
        preferred_skills=preferred,
        min_experience_years=min_years,
        responsibilities=responsibilities,
    )


def _bucket_by_inline_markers(jd_text: str) -> tuple[list[str], list[str]]:
    """Fallback for unstructured JDs: a skill mentioned near "nice to have"
    or "preferred" is treated as a preference, everything else as required."""
    skills = extract_all_skills(jd_text)
    lowered = jd_text.lower()
    required: list[str] = []
    preferred: list[str] = []
    for skill in skills:
        index = lowered.find(skill.lower())
        window = lowered[max(0, index - 60): index + 60] if index != -1 else ""
        if any(marker in window for marker in _PREFERRED_INLINE_MARKERS):
            preferred.append(skill)
        else:
            required.append(skill)
    return required, preferred


def _estimate_experience_years(text: str) -> float:
    matches = _YEARS_RE.findall(text)
    if not matches:
        return 0.0
    try:
        return max(float(m) for m in matches)
    except ValueError:
        return 0.0


def _estimate_experience_from_dates(text: str) -> float:
    """Fallback for resumes with no explicit "N years" statement: derive
    total experience from the span of work-history date ranges (e.g.
    "2019 - 2023", "Jan 2021 - Present")."""
    current_year = date.today().year
    starts: list[int] = []
    ends: list[int] = []
    for start_str, end_str in _YEAR_RANGE_RE.findall(text):
        start = int(start_str)
        end = current_year if end_str.lower() in ("present", "current") else int(end_str)
        if end < start:
            continue
        starts.append(start)
        ends.append(end)
    if not starts:
        return 0.0
    return float(max(ends) - min(starts))


def _extract_education(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    found: list[str] = []
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in _EDU_KEYWORDS) and len(line) < 160:
            found.append(line)
    return found[:5]


def _extract_bullets(text: str) -> list[str]:
    bullets = []
    for line in text.split("\n"):
        stripped = line.strip(" \t-•*•")
        if line.strip().startswith(("-", "*", "•", "•")) and stripped:
            bullets.append(stripped)
    return bullets


def _extract_work_history(text: str) -> list[WorkHistoryItem]:
    """Best-effort segmentation: split on the "Experience" section header,
    then treat consecutive non-bullet lines as company/role/duration and
    bullet lines as achievement bullets. Good enough for a fallback path;
    Gemini produces materially better structure when a key is configured."""
    lines = text.split("\n")
    start_idx = None
    end_idx = len(lines)
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if start_idx is None and low in _SECTION_HEADERS["experience"]:
            start_idx = i + 1
            continue
        if start_idx is not None and low in (
            _SECTION_HEADERS["education"] + _SECTION_HEADERS["skills"]
        ):
            end_idx = i
            break
    if start_idx is None:
        return []

    section = [ln for ln in lines[start_idx:end_idx] if ln.strip()]
    items: list[WorkHistoryItem] = []
    current: WorkHistoryItem | None = None
    duration_pat = re.compile(
        r"(20\d{2}|19\d{2}).{0,15}(20\d{2}|19\d{2}|present|current)", re.IGNORECASE
    )

    for line in section:
        stripped = line.strip(" \t-•*•")
        is_bullet = line.strip().startswith(("-", "*", "•", "•"))
        if is_bullet and current is not None:
            current.bullets.append(stripped)
            continue
        if duration_pat.search(line) and current is not None and not current.duration:
            current.duration = line.strip()
            continue
        # heuristic: a new non-bullet line starts a new job entry
        if current is not None:
            items.append(current)
        role, company = _split_role_company(stripped)
        current = WorkHistoryItem(company=company, role=role, duration="", bullets=[])
        dur = duration_pat.search(line)
        if dur:
            current.duration = dur.group(0)
    if current is not None:
        items.append(current)
    return items[:10]


def _split_role_company(line: str) -> tuple[str, str]:
    for sep in (" at ", " - ", " – ", " | ", ","):
        if sep in line:
            left, right = line.split(sep, 1)
            return left.strip(), right.strip()
    return line.strip(), ""


def _guess_candidate_name(text: str) -> str:
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        words = stripped.split()
        if 1 < len(words) <= 4 and all(w[:1].isupper() for w in words if w[:1].isalpha()):
            if "@" not in stripped and not any(ch.isdigit() for ch in stripped):
                return stripped
        break  # only ever consider the first non-empty line
    return ""


def _guess_role_title(jd_text: str) -> str:
    for line in jd_text.split("\n"):
        stripped = line.strip()
        if stripped and len(stripped) < 100:
            return stripped
    return ""


_service_singleton: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = GeminiService()
    return _service_singleton
