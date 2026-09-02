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
    "Excel": {"excel", "ms excel"},
    "Power BI": {"power bi", "powerbi"},
    "Tableau": {"tableau"},
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
