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

from app.config import get_settings
from app.schemas import ParsedJDData, ParsedResumeData, WorkHistoryItem
from app.services.taxonomy import extract_skills_from_text

logger = logging.getLogger(__name__)
settings = get_settings()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")
_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s*(?:of)?\s*(?:experience|exp)?", re.IGNORECASE
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


# ---------------------------------------------------------------------- #
# Heuristic fallback parsers (no external calls; deterministic; tested)
# ---------------------------------------------------------------------- #
def heuristic_parse_resume(raw_text: str) -> ParsedResumeData:
    email_match = _EMAIL_RE.search(raw_text)
    phone_match = _PHONE_RE.search(raw_text)
    skills = extract_skills_from_text(raw_text)
    experience_years = _estimate_experience_years(raw_text)
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


def heuristic_parse_jd(jd_text: str) -> ParsedJDData:
    skills = extract_skills_from_text(jd_text)
    min_years = _estimate_experience_years(jd_text)

    required, preferred = [], []
    lowered = jd_text.lower()
    preferred_markers = ("nice to have", "preferred", "bonus", "a plus")
    for skill in skills:
        # crude heuristic: if the skill's mention is near a "preferred/nice
        # to have" marker, bucket it as preferred; otherwise required.
        idx = lowered.find(skill.lower())
        window = lowered[max(0, idx - 60): idx + 60] if idx != -1 else ""
        if any(m in window for m in preferred_markers):
            preferred.append(skill)
        else:
            required.append(skill)

    role_title = _guess_role_title(jd_text)
    responsibilities = _extract_bullets(jd_text)[:8]

    return ParsedJDData(
        role_title=role_title,
        required_skills=required,
        preferred_skills=preferred,
        min_experience_years=min_years,
        responsibilities=responsibilities,
    )


def _estimate_experience_years(text: str) -> float:
    matches = _YEARS_RE.findall(text)
    if not matches:
        return 0.0
    try:
        return max(float(m) for m in matches)
    except ValueError:
        return 0.0


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
