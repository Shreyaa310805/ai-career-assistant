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
