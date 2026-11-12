"""ISSUE-15 — JD <-> resume skill matching. Pure functions, taxonomy-aware
(so "AWS" vs "Amazon Web Services" still match), used by ats_engine.py.

Matching runs in three tiers so that skills the taxonomy has never seen still
compare sensibly:

  1. canonical equality      "AWS" == "Amazon Web Services"  (synonym map)
  2. token-set equality      "React JS" == "react.js"        (punctuation/order)
  3. close string similarity "Snowflake" ~= "Snowflakes"     (ratio >= 0.87)

Tier 3 is deliberately tight — loose fuzzy matching would credit a candidate
for skills they do not have, which is worse than a false miss.
"""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.resumes.taxonomy import dedupe_normalized

SIMILARITY_THRESHOLD = 0.87

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
# Suffixes that carry no meaning when comparing technology names.
_NOISE_TOKENS = {"js", "lang", "language", "framework", "library", "db"}


def _tokens(skill: str) -> frozenset[str]:
    parts = [p for p in _TOKEN_SPLIT_RE.split(skill.lower()) if p]
    meaningful = frozenset(p for p in parts if p not in _NOISE_TOKENS)
    return meaningful or frozenset(parts)


def _flat(skill: str) -> str:
    return _TOKEN_SPLIT_RE.sub("", skill.lower())


def skills_equivalent(left: str, right: str) -> bool:
    """True when two canonical skill names denote the same skill."""
    if left.lower() == right.lower():
        return True
    if _tokens(left) == _tokens(right):
        return True
    left_flat, right_flat = _flat(left), _flat(right)
    if not left_flat or not right_flat:
        return False
    if left_flat == right_flat:
        return True
    # Very short names ("go", "r", "c#") are too collision-prone to fuzz.
    if min(len(left_flat), len(right_flat)) < 4:
        return False
    return SequenceMatcher(None, left_flat, right_flat).ratio() >= SIMILARITY_THRESHOLD


def match_skills(resume_skills: list[str], jd_skills: list[str]) -> tuple[list[str], list[str]]:
    """Returns (matched_skills, missing_skills), both normalized to
    canonical taxonomy names and de-duplicated, preserving the JD's
    original ordering (missing/matched skills are usually displayed in JD
    priority order)."""
    resume_norm = dedupe_normalized(resume_skills)
    jd_norm = dedupe_normalized(jd_skills)

    # Exact canonical hits are cheap; only unresolved JD skills pay for tiers 2-3.
    resume_exact = {s.lower() for s in resume_norm}

    matched: list[str] = []
    missing: list[str] = []
    for jd_skill in jd_norm:
        if jd_skill.lower() in resume_exact or any(
            skills_equivalent(jd_skill, resume_skill) for resume_skill in resume_norm
        ):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)
    return matched, missing


def skill_overlap_ratio(resume_skills: list[str], jd_skills: list[str]) -> float:
    if not jd_skills:
        return 1.0
    matched, _ = match_skills(resume_skills, jd_skills)
    return len(matched) / len(dedupe_normalized(jd_skills))


# --------------------------------------------------------------------------- #
# Interchangeable ("X or Y") requirements
#
# A JD line like "Python, Java or JavaScript" is a single requirement with
# three acceptable answers, but structured extraction flattens it into three
# separate skills. Scoring that flat list punishes a candidate who has one of
# them for "missing" the other two. These helpers recover the grouping from
# the JD's own wording so every alternative carries the same weight and the
# group counts once.
# --------------------------------------------------------------------------- #
# "or" may follow a comma (Oxford comma: "Python, Go, Java, or Node.js").
_OR_SEPARATOR = r"\s*,?\s+or\s+"
_ALTERNATIVE_SEPARATOR_RE = re.compile(r"\s*(?:/|\|)\s*|" + _OR_SEPARATOR + r"|\s*,\s*", re.IGNORECASE)
# A chain is two or more short phrases joined by those separators. Phrases are
# capped at three words so ordinary prose ("design or implement new features
# for the team") cannot swallow a whole sentence into one group. Commas are
# only accepted *before* the first "or", which is what makes "Python, Java or
# JavaScript" one requirement while "Docker, Kubernetes" stays two.
_ALTERNATIVE_PHRASE = r"[A-Za-z][\w.+#&-]*(?:[ ][A-Za-z][\w.+#&-]*){0,2}"
_ALTERNATIVE_CHAIN_RE = re.compile(
    _ALTERNATIVE_PHRASE
    + r"(?:\s*,\s*" + _ALTERNATIVE_PHRASE + r")*"
    + r"(?:\s*(?:/|\|)\s*|" + _OR_SEPARATOR + r")" + _ALTERNATIVE_PHRASE
    + r"(?:(?:\s*(?:/|\|)\s*|" + _OR_SEPARATOR + r")" + _ALTERNATIVE_PHRASE + r")*",
    re.IGNORECASE,
)


def _skill_in_phrase(phrase: str, canonical_skills: list[str]) -> str | None:
    """The JD skill this alternative refers to, or None if it names no skill.

    Requiring a known skill is what keeps ordinary prose containing "or" from
    being mistaken for an alternative requirement.
    """
    cleaned = phrase.strip().strip(".,;:()[]")
    if not cleaned:
        return None
    for skill in canonical_skills:
        if skills_equivalent(skill, cleaned):
            return skill
    lowered = f" {cleaned.lower()} "
    # Longest first so "Spring Boot" wins over "Spring" inside the same phrase.
    for skill in sorted(canonical_skills, key=len, reverse=True):
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lowered):
            return skill
    return None


def alternative_skill_groups(jd_text: str, jd_skills: list[str]) -> list[list[str]]:
    """Sets of JD skills the posting offers as interchangeable alternatives."""
    canonical = dedupe_normalized(jd_skills)
    if len(canonical) < 2 or not jd_text.strip():
        return []

    groups: list[list[str]] = []
    for chain in _ALTERNATIVE_CHAIN_RE.finditer(jd_text):
        members: list[str] = []
        seen: set[str] = set()
        for piece in _ALTERNATIVE_SEPARATOR_RE.split(chain.group(0)):
            skill = _skill_in_phrase(piece, canonical)
            if skill is not None and skill.lower() not in seen:
                seen.add(skill.lower())
                members.append(skill)
        if len(members) < 2:
            continue
        # A skill can appear in two chains ("Java or Kotlin", "Kotlin or Go");
        # merge so it ends up in exactly one group.
        overlapping = [g for g in groups if any(m.lower() in {s.lower() for s in g} for m in members)]
        for existing in overlapping:
            groups.remove(existing)
            members.extend(s for s in existing if s.lower() not in {m.lower() for m in members})
        groups.append(members)
    return groups


def requirement_units(jd_skills: list[str], jd_text: str) -> list[list[str]]:
    """JD skills split into requirements: an alternative group is one unit.

    Order follows the JD, a group taking the position of its first member.
    """
    canonical = dedupe_normalized(jd_skills)
    groups = alternative_skill_groups(jd_text, canonical)
    group_of = {skill.lower(): index for index, group in enumerate(groups) for skill in group}

    units: list[list[str]] = []
    emitted: set[int] = set()
    for skill in canonical:
        index = group_of.get(skill.lower())
        if index is None:
            units.append([skill])
        elif index not in emitted:
            emitted.add(index)
            units.append(list(groups[index]))
    return units


def match_requirements(
    resume_skills: list[str], jd_skills: list[str], jd_text: str = ""
) -> tuple[list[str], list[str]]:
    """match_skills(), with satisfied alternatives removed from `missing`.

    Holding Python when the JD asks for "Python or Java" is not a Java gap.
    """
    matched, missing = match_skills(resume_skills, jd_skills)
    if not jd_text.strip() or not missing:
        return matched, missing

    matched_keys = {skill.lower() for skill in matched}
    satisfied: set[str] = set()
    for unit in requirement_units(jd_skills, jd_text):
        if any(skill.lower() in matched_keys for skill in unit):
            satisfied.update(skill.lower() for skill in unit)
    return matched, [skill for skill in missing if skill.lower() not in satisfied]


def requirement_match_ratio(
    resume_skills: list[str], jd_skills: list[str], jd_text: str = ""
) -> float:
    """Fraction of JD *requirements* met, counting an alternative group once."""
    if not jd_skills:
        return 1.0
    units = requirement_units(jd_skills, jd_text)
    if not units:
        return 1.0
    matched, _ = match_skills(resume_skills, jd_skills)
    matched_keys = {skill.lower() for skill in matched}
    satisfied = sum(1 for unit in units if any(skill.lower() in matched_keys for skill in unit))
    return satisfied / len(units)


# --------------------------------------------------------------------------- #
# Requirement-level evaluation used by the role match score
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Requirement:
    """One JD requirement: a single skill, or a set of equal alternatives.

    `tier` is "required" when any alternative was listed as required, so an
    either/or line split across the two lists still counts once, at the
    stronger tier. `satisfied_by` lists the alternatives the resume holds.
    """

    skills: tuple[str, ...]
    tier: str
    satisfied_by: tuple[str, ...]

    @property
    def met(self) -> bool:
        return bool(self.satisfied_by)

    @property
    def is_alternative_group(self) -> bool:
        return len(self.skills) > 1

    @property
    def unmet_alternatives(self) -> tuple[str, ...]:
        held = {skill.lower() for skill in self.satisfied_by}
        return tuple(skill for skill in self.skills if skill.lower() not in held)


def evaluate_requirements(
    resume_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str],
    jd_text: str = "",
) -> list[Requirement]:
    """Every JD requirement with its tier and the resume skills that meet it.

    Requirements come back in JD order (required list first, then preferred),
    an alternative group taking the position of its first member. Each JD
    skill belongs to exactly one requirement, and every member of a group
    carries equal weight: the group is met when *any* one of them is held.
    """
    required = dedupe_normalized(required_skills)
    required_keys = {skill.lower() for skill in required}
    preferred = [s for s in dedupe_normalized(preferred_skills) if s.lower() not in required_keys]
    all_skills = required + preferred
    if not all_skills:
        return []

    matched, _ = match_skills(resume_skills, all_skills)
    matched_keys = {skill.lower() for skill in matched}

    requirements: list[Requirement] = []
    for unit in requirement_units(all_skills, jd_text):
        tier = "required" if any(skill.lower() in required_keys for skill in unit) else "preferred"
        requirements.append(
            Requirement(
                skills=tuple(unit),
                tier=tier,
                satisfied_by=tuple(skill for skill in unit if skill.lower() in matched_keys),
            )
        )
    return requirements
