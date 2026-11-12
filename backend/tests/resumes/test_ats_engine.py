import pytest

from app.schemas.resume import ParsedJDData, ParsedResumeData, WorkHistoryItem
from app.services.resumes.ats_engine import calculate_ats_score, calculate_match_score, generate_suggestions
from app.services.resumes.gemini_service import heuristic_parse_jd, heuristic_parse_resume
from app.services.resumes.matching import (
    alternative_skill_groups,
    match_requirements,
    match_skills,
)
from tests.resumes.conftest import SAMPLE_RESUME_TEXT_LINES


def test_heuristic_parse_resume_extracts_core_fields():
    raw_text = "\n".join(SAMPLE_RESUME_TEXT_LINES)
    parsed = heuristic_parse_resume(raw_text)
    assert parsed.email == "jane.doe@example.com"
    assert "Python" in parsed.skills
    assert "FastAPI" in parsed.skills
    assert "Docker" in parsed.skills
    assert len(parsed.work_history) >= 1
    assert parsed.work_history[0].bullets


def test_heuristic_parse_jd_extracts_skills_and_experience(sample_jd_text):
    jd = heuristic_parse_jd(sample_jd_text)
    assert "Python" in jd.required_skills or "Python" in jd.preferred_skills
    assert jd.min_experience_years == 5.0
    assert "Kubernetes" in jd.preferred_skills


def test_match_skills_uses_taxonomy_synonyms():
    matched, missing = match_skills(
        resume_skills=["python", "Amazon Web Services"],
        jd_skills=["Python", "AWS", "Docker"],
    )
    assert "Python" in matched
    assert "AWS" in matched  # matched via synonym normalization
    assert "Docker" in missing


def test_calculate_ats_score_rewards_complete_resume():
    parsed = ParsedResumeData(
        candidate_name="Jane Doe",
        email="jane@example.com",
        phone="+1 555 123 4567",
        skills=["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Git", "AWS", "SQL"],
        experience_years=4.5,
        work_history=[
            WorkHistoryItem(
                company="Tech Corp",
                role="Software Engineer",
                duration="2022-Present",
                bullets=["Improved throughput by 40%", "Cut costs by 20%"],
            )
        ],
        education=["B.S. Computer Science"],
    )
    raw_text = "Experience Education Skills " + " ".join(parsed.skills) * 20
    score, components = calculate_ats_score(raw_text, parsed)
    assert 0 <= score <= 100
    assert score > 60
    assert set(components) == {
        "contact_completeness", "section_coverage", "skills_listed",
        "quantified_impact", "length_check", "work_history_structure",
    }


def test_calculate_ats_score_penalizes_sparse_resume():
    parsed = ParsedResumeData()
    score, _ = calculate_ats_score("just a name, nothing else", parsed)
    assert score < 30


def test_calculate_match_score_weighs_required_over_preferred():
    resume = ParsedResumeData(skills=["Python", "FastAPI"], experience_years=5)
    jd = ParsedJDData(
        required_skills=["Python", "FastAPI", "Docker", "AWS"],
        preferred_skills=["Kubernetes"],
        min_experience_years=5,
    )
    score, matched, missing, components = calculate_match_score(resume, jd)
    assert "Python" in matched and "FastAPI" in matched
    assert "Docker" in missing and "AWS" in missing
    assert 0 <= score <= 100
    assert components["experience_match_pct"] == 100.0


def test_generate_suggestions_flags_missing_required_skills():
    resume = ParsedResumeData(skills=["Python"], experience_years=2)
    jd = ParsedJDData(required_skills=["Python", "Docker"], min_experience_years=5)
    ats_components = {"quantified_impact": 20, "contact_completeness": 15, "section_coverage": 20}
    suggestions = generate_suggestions(resume, jd, missing_skills=["Docker"], ats_components=ats_components)
    categories = [s.category for s in suggestions]
    assert "Formatting & Keywords" in categories
    assert any(s.impact == "High" for s in suggestions)


# --------------------------------------------------------------------------
# Open-vocabulary extraction: skills outside SKILL_SYNONYMS must still count.
# Before this, anything the taxonomy had not memorized was dropped from both
# sides of the comparison, which made every score look pre-baked.
# --------------------------------------------------------------------------
JD_WITH_UNKNOWN_SKILLS = """Senior Analytics Engineer

Requirements
- 4+ years of experience building data platforms
- Snowflake, dbt, Apache Airflow
- Terraform and AWS

Preferred Qualifications
- Databricks
- Looker
"""


def test_jd_parsing_keeps_skills_absent_from_the_taxonomy():
    jd = heuristic_parse_jd(JD_WITH_UNKNOWN_SKILLS)
    for skill in ("Snowflake", "dbt", "Apache Airflow"):
        assert skill in jd.required_skills, f"{skill} was dropped from required_skills"
    # An explicit "Preferred Qualifications" header beats proximity guessing.
    assert "Databricks" in jd.preferred_skills
    assert "Looker" in jd.preferred_skills
    assert "Databricks" not in jd.required_skills
    # Known skills still normalize through the synonym map.
    assert "AWS" in jd.required_skills
    assert jd.min_experience_years == 4.0


def test_match_score_reflects_unknown_skills_on_both_sides():
    resume = ParsedResumeData(skills=["Snowflake", "dbt", "Python"], experience_years=4)
    jd = heuristic_parse_jd(JD_WITH_UNKNOWN_SKILLS)
    _score, matched, missing, _components = calculate_match_score(resume, jd)
    assert "Snowflake" in matched and "dbt" in matched
    assert "Apache Airflow" in missing and "Terraform" in missing


def test_resume_skills_section_captures_unlisted_technologies():
    raw_text = "\n".join([
        "Alex Rivera",
        "alex@example.com",
        "",
        "Technical Skills",
        "Snowflake, dbt, Apache Airflow, Python, Great Expectations",
        "",
        "Experience",
        "Analytics Engineer at DataCo",
        "2021 - Present",
        "- Modeled 200+ dbt sources",
    ])
    parsed = heuristic_parse_resume(raw_text)
    for skill in ("Snowflake", "dbt", "Apache Airflow", "Great Expectations"):
        assert skill in parsed.skills, f"{skill} missing from parsed resume skills"
    assert "Python" in parsed.skills  # taxonomy hits still work


def test_prose_is_not_mistaken_for_a_skill():
    jd = heuristic_parse_jd(
        "Backend Engineer\n\n"
        "Requirements\n"
        "- You will be responsible for designing and shipping resilient services\n"
        "- Strong knowledge of Python\n"
    )
    all_skills = jd.required_skills + jd.preferred_skills
    assert "Python" in all_skills
    assert not any(len(skill.split()) > 4 for skill in all_skills)
    assert not any(skill.lower().startswith("you will") for skill in all_skills)


def test_match_skills_tolerates_punctuation_and_near_spellings():
    matched, missing = match_skills(
        resume_skills=["React JS", "Snowflakes", "Node"],
        jd_skills=["React.js", "Snowflake", "Node.js", "Rust"],
    )
    assert "React.js" in matched or "React" in matched
    assert "Snowflake" in matched
    assert "Rust" in missing


def test_match_skills_does_not_confuse_short_names():
    matched, missing = match_skills(resume_skills=["Go"], jd_skills=["R", "C#"])
    assert matched == []
    assert set(missing) == {"R", "C#"}


# --------------------------------------------------------------------- #
# Dynamic explanations
# --------------------------------------------------------------------- #
from app.services.resumes.ats_engine import explain_ats_components, summarize_ats_score  # noqa: E402


def _explain(parsed, raw_text="Experience Education Skills"):
    _score, components = calculate_ats_score(raw_text, parsed)
    return explain_ats_components(raw_text, parsed, components), components


def test_explanations_distinguish_missing_phone_from_missing_email():
    no_phone, _ = _explain(ParsedResumeData(email="a@b.com"))
    no_email, _ = _explain(ParsedResumeData(phone="555 123 4567"))
    neither, _ = _explain(ParsedResumeData())
    assert "no phone" in no_phone["contact_completeness"]
    assert "no email" in no_email["contact_completeness"]
    assert "Neither" in neither["contact_completeness"]


def test_explanations_count_bullets_with_metrics():
    parsed = ParsedResumeData(
        work_history=[
            WorkHistoryItem(
                company="A",
                role="Dev",
                bullets=["Cut latency by 30%", "Served 2M users", "Wrote docs", "Mentored peers", "Ran demos"],
            )
        ]
    )
    explanations, _ = _explain(parsed)
    assert explanations["quantified_impact"] == (
        "2 of 5 achievement statements (40%) include a measurable result; 50% or more earns full points."
    )


def test_explanations_name_missing_sections_and_word_count():
    explanations, _ = _explain(ParsedResumeData(), raw_text="Experience only here")
    assert "1 of 3" in explanations["section_coverage"]
    assert "Education" in explanations["section_coverage"]
    assert "Skills" in explanations["section_coverage"]
    assert "3 words" in explanations["length_check"]


def test_explanations_report_jd_skill_overlap():
    parsed = ParsedResumeData(skills=["Python", "Docker"])
    jd = ParsedJDData(required_skills=["Python", "Docker", "AWS"], preferred_skills=["Kubernetes"])
    _score, components = calculate_ats_score("Experience Education Skills", parsed, jd)
    text = explain_ats_components("Experience Education Skills", parsed, components, jd)
    assert text["skills_listed"].startswith("2 of 4 requirements")


def test_summary_names_strongest_check_and_biggest_leak():
    components = {
        "contact_completeness": 15.0,
        "section_coverage": 20.0,
        "skills_listed": 10.0,
        "quantified_impact": 0.0,
        "length_check": 15.0,
        "work_history_structure": 15.0,
    }
    summary = summarize_ats_score(components)
    assert "quantified impact" in summary
    assert "0 of 20" in summary
    assert "strongest" in summary


def test_summary_handles_perfect_and_empty_scores():
    perfect = {
        "contact_completeness": 15.0,
        "section_coverage": 20.0,
        "skills_listed": 15.0,
        "quantified_impact": 20.0,
        "length_check": 15.0,
        "work_history_structure": 15.0,
    }
    assert "full marks" in summarize_ats_score(perfect)
    assert summarize_ats_score({}) == ""


# --------------------------------------------------------------------------
# Interchangeable ("X or Y") requirements
# --------------------------------------------------------------------------
_ALTERNATIVES_JD = (
    "Requirements:\n"
    "- Strong programming in Python, Java or JavaScript\n"
    "- Experience with PostgreSQL or MySQL\n"
    "- You will design or implement new features\n"
    "- Docker required\n"
)


def test_alternatives_are_one_requirement_any_of_them_satisfies():
    jd_skills = ["Python", "Java", "JavaScript", "PostgreSQL", "MySQL", "Docker"]
    groups = alternative_skill_groups(_ALTERNATIVES_JD, jd_skills)
    assert ["Python", "Java", "JavaScript"] in groups
    assert ["PostgreSQL", "MySQL"] in groups
    # "design or implement" is prose, not a skill requirement.
    assert all("Docker" not in group for group in groups)

    matched, missing = match_requirements(["Python", "Docker", "MySQL"], jd_skills, _ALTERNATIVES_JD)
    assert set(matched) == {"Python", "Docker", "MySQL"}
    assert missing == []  # every requirement is met by one of its alternatives


def test_each_alternative_carries_the_same_weight_in_the_match_score():
    jd = ParsedJDData(required_skills=["Python", "Java", "JavaScript", "Docker"])
    jd_text = "Strong programming in Python, Java or JavaScript\nDocker required"
    with_python, _m, _x, _c = calculate_match_score(
        ParsedResumeData(skills=["Python", "Docker"]), jd, jd_text
    )
    with_javascript, _m, _x, _c = calculate_match_score(
        ParsedResumeData(skills=["JavaScript", "Docker"]), jd, jd_text
    )
    assert with_python == with_javascript
    # Two requirements, both met — not "two of four skills".
    assert with_python == 100.0


# --------------------------------------------------------------------------
# Role match formula: traceable weights, alternatives, covered options
# --------------------------------------------------------------------------
def test_match_score_formula_is_traceable():
    from app.services.resumes.ats_engine import explain_match_score, match_score_details

    jd = ParsedJDData(
        required_skills=["Go", "Python", "Java", "Docker", "Kubernetes"],
        preferred_skills=["Terraform", "AWS"],
        min_experience_years=4,
    )
    jd_text = "Go, Python or Java\nDocker\nKubernetes\nNice to have: Terraform, AWS"
    resume = ParsedResumeData(skills=["Python", "Docker", "AWS"], experience_years=2)

    score, matched, missing, components = calculate_match_score(resume, jd, jd_text)
    # required: 2 of 3 requirements (Go/Python/Java counts once) -> 65 × 2/3
    # preferred: 1 of 2 -> 15 × 1/2 ; experience: 2/4 -> 20 × 0.5
    assert score == round(65 * 2 / 3 + 15 * 0.5 + 20 * 0.5, 2)
    assert components["required_met"] == 2 and components["required_total"] == 3
    assert components["required_points"] + components["preferred_points"] + components[
        "experience_points"
    ] == pytest.approx(score, abs=0.02)
    # Go and Java are covered by Python: not gaps.
    assert missing == ["Kubernetes", "Terraform"]

    details = match_score_details(resume, jd, jd_text)
    assert details.covered_alternatives == {"Go": ["Python"], "Java": ["Python"]}
    lines = explain_match_score(details)
    assert set(lines) == {"formula", "required", "preferred", "experience", "total"}
    assert "Go / Python / Java" in lines["required"] and "met by Python" in lines["required"]


def test_unmet_alternatives_are_listed_together_with_equal_weight():
    jd = ParsedJDData(required_skills=["Docker", "Go", "Python", "Java"])
    jd_text = "Docker\nOne of Go, Python or Java"
    score, _m, missing, _c = calculate_match_score(ParsedResumeData(skills=["Docker"]), jd, jd_text)
    assert score == 50.0  # 1 of 2 requirements, not 1 of 4 skills
    assert missing == ["Go", "Python", "Java"]


def test_tiers_the_jd_omits_are_redistributed_not_free():
    jd = ParsedJDData(required_skills=["Python", "Docker"])  # no preferred, no years
    score, *_ = calculate_match_score(ParsedResumeData(skills=["Python"]), jd)
    assert score == 50.0


# --------------------------------------------------------------------------
# Quantified impact is read from the resume text itself
# --------------------------------------------------------------------------
_UNBULLETED_RESUME = """Asha Rao
asha@example.com | +91 90000 22222
EXPERIENCE
Backend Intern — Acme Labs | Jan 2025 – Jun 2025: Reduced API latency by 35% by adding
Redis caching and query indexes across the orders service.
Built an internal Python3 dashboard used by the operations team every day.
PROJECTS
Ride Tracker — Scaled a FastAPI service to 10k daily users with Docker on AWS EC2.
Portfolio site built with Next.js and deployed on Vercel for personal branding.
EDUCATION
B.Tech Computer Science | 2026 | CGPA 8.9/10
SKILLS
Python, FastAPI, Docker
"""


def test_quantified_impact_reads_unbulleted_experience_and_projects():
    from app.services.resumes.ats_engine import achievement_statements, is_quantified

    statements = achievement_statements(_UNBULLETED_RESUME)
    assert len(statements) == 4
    assert [is_quantified(s) for s in statements] == [True, False, True, False]

    # The parser found no bullets at all — the old behaviour scored this 0.
    parsed = ParsedResumeData(email="asha@example.com", skills=["Python"])
    _score, components = calculate_ats_score(_UNBULLETED_RESUME, parsed)
    assert components["quantified_impact"] == 20.0  # 2 of 4 = 50% -> full points


def test_dates_and_version_numbers_are_not_metrics():
    from app.services.resumes.ats_engine import is_quantified

    assert not is_quantified("Software Engineer, Jan 2022 – Present, built Python3 services on EC2")
    assert not is_quantified("Worked 2019-2021 on GPT-4 and HTML5 tooling")
    assert is_quantified("Cut cloud spend by $12k per month")
    assert is_quantified("Doubled checkout conversion for the mobile app")


def test_skill_gap_priority_gives_alternatives_equal_index_and_covered_ones_last():
    from app.api.routes.career import _priority_for_missing_skills

    jd_text = "Kubernetes\nGo, Rust or Java\nTerraform"
    ranked = _priority_for_missing_skills(
        ["Kubernetes", "Go", "Rust", "Java", "Terraform"], "Backend Engineer", jd_text,
        covered={"Scala": ["Python"]},
    )
    scores = {item["skill"]: item["priority_score"] for item in ranked}
    # Three requirements: 0.9, 0.7, 0.5 — the whole group shares slot 2.
    assert scores["Kubernetes"] == 0.9
    assert scores["Go"] == scores["Rust"] == scores["Java"] == 0.7
    assert scores["Terraform"] == 0.5
    assert ranked[-1]["skill"] == "Scala" and ranked[-1]["priority_score"] == 0.1


def test_oxford_comma_or_list_is_one_requirement_of_any_length():
    jd_text = "Proficiency in at least one backend language (Python, Go, Java, or Node.js).\nDocker"
    skills = ["Python", "Go", "Java", "Node.js", "Docker"]
    assert alternative_skill_groups(jd_text, skills) == [["Python", "Go", "Java", "Node.js"]]

    jd = ParsedJDData(required_skills=skills)
    score, _m, missing, _c = calculate_match_score(ParsedResumeData(skills=["Java", "Docker"]), jd, jd_text)
    assert score == 100.0 and missing == []
    _s, _m, missing, _c = calculate_match_score(ParsedResumeData(skills=["Docker"]), jd, jd_text)
    assert missing == ["Python", "Go", "Java", "Node.js"]


def test_roadmap_moves_covered_alternatives_to_lowest_priority_even_for_old_reports():
    from types import SimpleNamespace

    from app.api.routes.career import _covered_alternatives, _priority_for_missing_skills

    jd_text = "Python, Go, Java, or Node.js\nKubernetes"
    # An old report that still lists Go etc. as missing and has no covered_alternatives.
    report = SimpleNamespace(
        matched_skills=["Java"], missing_skills=["Python", "Go", "Node.js", "Kubernetes"], score_breakdown={}
    )
    missing = list(report.missing_skills)
    covered = _covered_alternatives(report, missing, {"java": "Java"}, jd_text)
    assert set(covered) == {"Python", "Go", "Node.js"}
    remaining = [s for s in missing if s not in covered]
    ranked = _priority_for_missing_skills(remaining, "Backend Engineer", jd_text, covered)
    assert ranked[0]["skill"] == "Kubernetes" and ranked[0]["priority"] == "High"
    assert all(item["priority_score"] == 0.1 for item in ranked[1:])
