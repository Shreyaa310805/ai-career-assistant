from app.schemas.resume import ParsedJDData, ParsedResumeData, WorkHistoryItem
from app.services.resumes.ats_engine import calculate_ats_score, calculate_match_score, generate_suggestions
from app.services.resumes.gemini_service import heuristic_parse_jd, heuristic_parse_resume
from app.services.resumes.matching import match_skills
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
    jd = ParsedJDData(required_skills=["Python", "FastAPI", "Docker"], preferred_skills=["AWS"])
    score, components = calculate_ats_score(raw_text, parsed, jd)
    assert 0 <= score <= 100
    assert score > 60
    assert set(components) == {
        "jd_keyword_coverage", "contact_completeness", "section_coverage",
        "quantified_impact", "length_check", "work_history_structure",
    }


def test_calculate_ats_score_penalizes_sparse_resume():
    parsed = ParsedResumeData()
    jd = ParsedJDData(required_skills=["Python"])
    score, _ = calculate_ats_score("just a name, nothing else", parsed, jd)
    assert score < 30


def test_calculate_ats_score_varies_by_jd():
    parsed = ParsedResumeData(
        candidate_name="Jane Doe",
        email="jane@example.com",
        phone="+1 555 123 4567",
        skills=["Python", "FastAPI", "Docker"],
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
    raw_text = "Experience Education Skills " + " ".join(parsed.skills) * 10

    matching_jd = ParsedJDData(required_skills=["Python", "FastAPI", "Docker"])
    unrelated_jd = ParsedJDData(required_skills=["Salesforce", "Tableau", "SAP"])

    score_matching, _ = calculate_ats_score(raw_text, parsed, matching_jd)
    score_unrelated, _ = calculate_ats_score(raw_text, parsed, unrelated_jd)

    assert score_matching != score_unrelated
    assert score_matching > score_unrelated


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
