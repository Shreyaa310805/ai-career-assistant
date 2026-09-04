"""
Shared skills taxonomy used by both the heuristic parser fallback
(gemini_service.py) and the ATS/matching engine (ats_engine.py, matching.py).

Keeping one canonical list + synonym map means "AWS" in a resume and
"Amazon Web Services" in a JD are recognized as the same skill everywhere
in the pipeline.
"""
import re

# canonical_skill -> set of surface forms (lowercase) that should map to it
SKILL_SYNONYMS: dict[str, set[str]] = {
    "Python": {"python", "python3"},
    "JavaScript": {"javascript", "js", "es6", "ecmascript"},
    "TypeScript": {"typescript", "ts"},
    "Java": {"java"},
    "C++": {"c++", "cpp"},
    "C#": {"c#", "csharp"},
    "Go": {"golang", "go lang", "go"},
    "SQL": {"sql"},
    "PostgreSQL": {"postgresql", "postgres", "psql"},
    "MySQL": {"mysql"},
    "MongoDB": {"mongodb", "mongo"},
    "FastAPI": {"fastapi", "fast api"},
    "Django": {"django"},
    "Flask": {"flask"},
    "React": {"react", "react.js", "reactjs"},
    "Next.js": {"next.js", "nextjs"},
    "Node.js": {"node.js", "nodejs", "node"},
    "Docker": {"docker", "containerization"},
    "Kubernetes": {"kubernetes", "k8s"},
    "AWS": {"aws", "amazon web services"},
    "Azure": {"azure", "microsoft azure"},
    "GCP": {"gcp", "google cloud", "google cloud platform"},
    "CI/CD": {"ci/cd", "cicd", "continuous integration", "continuous deployment"},
    "Git": {"git"},
    "REST": {"rest", "restful", "rest api", "restful api"},
    "GraphQL": {"graphql"},
    "Pydantic": {"pydantic"},
    "SQLAlchemy": {"sqlalchemy"},
    "Redis": {"redis"},
    "Machine Learning": {"machine learning", "ml"},
    "Deep Learning": {"deep learning", "dl"},
    "TensorFlow": {"tensorflow"},
    "PyTorch": {"pytorch"},
    "NLP": {"nlp", "natural language processing"},
    "HTML": {"html", "html5"},
    "CSS": {"css", "css3", "tailwind", "tailwind css"},
    "Linux": {"linux", "unix"},
    "Agile": {"agile", "scrum"},
    "Microservices": {"microservices", "microservice architecture"},
    "gRPC": {"grpc"},
    "Terraform": {"terraform", "iac", "infrastructure as code"},
    "Jenkins": {"jenkins"},
    "Kafka": {"kafka", "apache kafka"},
    "Spark": {"spark", "apache spark"},
    "R": {" r ", "r programming"},
    "Excel": {"excel", "ms excel", "microsoft excel"},
    "Power BI": {"power bi", "powerbi"},
    "Tableau": {"tableau"},
    # Non-technical / productivity & soft skills — ATS matching should not
    # be limited to technical keywords.
    "Microsoft Word": {"ms word", "microsoft word", "word processing", "word"},
    "PowerPoint": {"powerpoint", "ms powerpoint", "microsoft powerpoint", "power point"},
    "Google Sheets": {"google sheets"},
    "Google Docs": {"google docs"},
    "Google Slides": {"google slides"},
    "Microsoft Office": {"microsoft office", "ms office", "office suite"},
    "Communication": {"communication", "communication skills", "verbal communication", "written communication"},
    "Leadership": {"leadership", "leadership skills", "team leadership"},
    "Teamwork": {"teamwork", "team player", "collaboration"},
    "Time Management": {"time management"},
    "Problem Solving": {"problem solving", "problem-solving"},
    "Critical Thinking": {"critical thinking"},
    "Project Management": {"project management"},
    "Presentation Skills": {"presentation skills", "public speaking"},
    "Customer Service": {"customer service"},
    "Negotiation": {"negotiation"},
    "Adaptability": {"adaptability", "flexibility"},
    # Canonical name is "Organizational Skills", not the bare word
    # "organization" — too common in unrelated contexts (company names, etc).
    "Organizational Skills": {"organizational skills", "organisational skills"},
}

_SURFACE_TO_CANONICAL: dict[str, str] = {}
for canonical, surfaces in SKILL_SYNONYMS.items():
    _SURFACE_TO_CANONICAL[canonical.lower()] = canonical
    for s in surfaces:
        _SURFACE_TO_CANONICAL[s.strip().lower()] = canonical

# sort longest-first so multi-word surface forms match before their
# single-word substrings do (e.g. "google cloud platform" before "go")
_ALL_SURFACES = sorted(_SURFACE_TO_CANONICAL.keys(), key=len, reverse=True)


def normalize_skill(raw: str) -> str:
    """Map any surface form to its canonical skill name; title-case unknowns."""
    key = raw.strip().lower()
    return _SURFACE_TO_CANONICAL.get(key, raw.strip())


def extract_skills_from_text(text: str) -> list[str]:
    """Heuristic keyword-spotting extraction against the taxonomy. Returns
    canonical skill names, de-duplicated, in first-seen order."""
    lowered = f" {text.lower()} "
    found: list[str] = []
    seen: set[str] = set()
    for surface in _ALL_SURFACES:
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(surface.strip()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lowered):
            canonical = _SURFACE_TO_CANONICAL[surface]
            if canonical not in seen:
                seen.add(canonical)
                found.append(canonical)
    return found


def dedupe_normalized(skills: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in skills:
        canonical = normalize_skill(s)
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            out.append(canonical)
    return out


# ---------------------------------------------------------------------------
# Open-vocabulary skill discovery
#
# The synonym map above is a *canonicalization* layer, not the universe of
# skills. Restricting extraction to it meant anything it had never heard of
# ("Snowflake", "dbt", "Airflow") was silently dropped from both the resume
# and the JD, which is what made match scores look pre-baked. The functions
# below read the document's own skills/requirements sections and keep the
# candidates found there, whether or not the taxonomy recognizes them.
# ---------------------------------------------------------------------------

_SECTION_HEADER_RE = re.compile(
    r"^\s*(?:[-•*]\s*)?"
    r"(technical skills|core competencies|technologies|tech stack|tools|skills"
    r"|requirements|required skills|qualifications|minimum qualifications"
    r"|what you.ll need|must have|preferred qualifications|preferred skills"
    r"|nice to have|bonus points|good to have)"
    r"\s*:?\s*$",
    re.IGNORECASE,
)

# A header that ends a skills/requirements block.
_TERMINATING_HEADER_RE = re.compile(
    r"^\s*(?:experience|work experience|professional experience|employment"
    r"|education|academic background|projects|certifications|responsibilities"
    r"|what you.ll do|about us|about the role|benefits|perks|summary|objective"
    r"|awards|publications|interests|references)\s*:?\s*$",
    re.IGNORECASE,
)

_CANDIDATE_SPLIT_RE = re.compile(r"[,;|/•·]|\s+and\s+|\s{3,}")

# Words that signal prose rather than a skill name.
_PROSE_MARKERS = {
    "the", "and", "with", "you", "your", "our", "we", "will", "have", "has",
    "are", "is", "be", "to", "of", "in", "for", "on", "as", "an", "a", "or",
    "that", "this", "their", "them", "who", "able", "ability", "years", "year",
    "experience", "strong", "excellent", "good", "solid", "proven", "working",
    "knowledge", "understanding", "familiarity", "proficiency", "proficient",
    "skills", "skill", "plus", "must", "should", "would", "can", "using",
    "such", "etc", "including", "e.g", "i.e", "at", "least", "minimum",
}

_ALLOWED_SKILL_CHARS_RE = re.compile(r"^[A-Za-z0-9 .+#/&_'\-]+$")


def _is_plausible_skill(candidate: str) -> bool:
    """Reject prose fragments; keep short, noun-phrase-shaped tokens."""
    text = candidate.strip(" \t.:;-–—•*()[]")
    if not (2 <= len(text) <= 40):
        return False
    if not _ALLOWED_SKILL_CHARS_RE.match(text):
        return False
    words = text.split()
    if not (1 <= len(words) <= 4):
        return False
    lowered = [w.lower().strip(".,") for w in words]
    # A phrase built mostly of filler words is a sentence fragment, not a skill.
    if sum(1 for w in lowered if w in _PROSE_MARKERS) > len(lowered) / 2:
        return False
    if len(words) == 1 and lowered[0] in _PROSE_MARKERS:
        return False
    # Require at least one letter; pure version numbers or years are noise.
    if not any(ch.isalpha() for ch in text):
        return False
    return True


def _iter_section_bodies(text: str):
    """Yield the lines belonging to each skills/requirements section."""
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        if _SECTION_HEADER_RE.match(lines[index]):
            body: list[str] = []
            index += 1
            while index < len(lines):
                line = lines[index]
                if _SECTION_HEADER_RE.match(line) or _TERMINATING_HEADER_RE.match(line):
                    break
                if line.strip():
                    body.append(line)
                elif body:
                    # A blank line ends an inline skills list.
                    break
                index += 1
            if body:
                yield body
            continue
        index += 1


def extract_skills_from_sections(text: str) -> list[str]:
    """Collect skill candidates from the document's own skills/requirements
    sections, normalized through the taxonomy but not limited to it."""
    found: list[str] = []
    seen: set[str] = set()
    for body in _iter_section_bodies(text):
        for line in body:
            stripped = line.strip(" \t-•*·")
            for raw in _CANDIDATE_SPLIT_RE.split(stripped):
                if not _is_plausible_skill(raw):
                    continue
                canonical = normalize_skill(raw.strip(" \t.:;-–—•*()[]"))
                key = canonical.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(canonical)
    return found


def extract_all_skills(text: str) -> list[str]:
    """Union of taxonomy keyword-spotting and open-vocabulary section
    discovery, de-duplicated on canonical name in first-seen order.

    Taxonomy hits come first: they are the highest-confidence signal and the
    ordering matters downstream (matched/missing lists are displayed in this
    order, and career.py treats position as a relevance proxy)."""
    return dedupe_normalized(
        [*extract_skills_from_text(text), *extract_skills_from_sections(text)]
    )
