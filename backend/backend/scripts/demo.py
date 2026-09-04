"""
Standalone end-to-end demo of Module 1, with NO running server and NO
other module required — this is the "Complete Resume Analyzer that can
work with sample JD/resume data independently" deliverable called for in
the project brief.

Run:
    python scripts/demo.py

It generates a sample resume (PDF, via PyMuPDF) and a sample JD in memory,
then drives extraction -> parsing -> ATS scoring -> matching ->
explainable suggestions -> versioning, printing the results at each stage.
"""
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.resume_session import Base
from app.models.resume import AtsReport, Resume
from app.services.resumes.ats_engine import calculate_ats_score, calculate_match_score, generate_suggestions
from app.services.resumes.extraction import extract_jd_text, extract_text_from_pdf
from app.services.resumes.gemini_service import get_gemini_service
from app.services.resumes.storage import new_resume_id
from app.services.resumes.versioning import diff_versions, recommend_version

SAMPLE_RESUME_LINES = [
    "Jane Doe",
    "jane.doe@example.com | +1 555-123-4567",
    "",
    "Skills",
    "Python, React, Git, HTML, CSS",
    "",
    "Experience",
    "Software Engineer at Tech Corp",
    "2022 - Present",
    "- Built internal tools with React",
    "- Fixed bugs reported by QA",
    "",
    "Education",
    "B.S. Computer Science, State University",
]

SAMPLE_JD_TEXT = (
    "Senior Backend Developer\n\n"
    "We are looking for a Senior Backend Developer with 5+ years of "
    "experience in Python, FastAPI, Docker, and AWS. PostgreSQL and "
    "CI/CD experience required. Kubernetes is a nice to have.\n"
)


def _make_sample_pdf_bytes(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "\n".join(lines), fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _print_header(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


async def main() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    gemini = get_gemini_service()
    print(f"Gemini enabled: {gemini.using_llm} "
          f"({'live Gemini calls' if gemini.using_llm else 'heuristic fallback parser'})")

    # --- ISSUE-10/11: upload + extract -----------------------------------
    _print_header("1. Resume upload & text extraction (ISSUE-10/11)")
    pdf_bytes = _make_sample_pdf_bytes(SAMPLE_RESUME_LINES)
    raw_text = extract_text_from_pdf(pdf_bytes)
    print(raw_text)

    # --- ISSUE-13: structured parsing --------------------------------------
    _print_header("2. Structured resume parsing (ISSUE-13)")
    parsed_resume = gemini.parse_resume(raw_text)
    print(parsed_resume.model_dump_json(indent=2))

    application_id = "11111111-1111-1111-1111-111111111111"
    resume_id = new_resume_id()

    async with session_factory() as session:
        resume = Resume(
            id=resume_id,
            application_id=application_id,
            version_number=1,
            file_url=f"https://storage.example.com/resumes/{resume_id}.pdf",
            raw_text=raw_text,
            parsed_data=parsed_resume.model_dump(),
            is_best_version=True,
        )
        session.add(resume)
        await session.commit()

    # --- ISSUE-12/13: JD parsing --------------------------------------------
    _print_header("3. JD text extraction & parsing (ISSUE-12/13)")
    jd_text = extract_jd_text(SAMPLE_JD_TEXT)
    parsed_jd = gemini.parse_jd(jd_text)
    print(parsed_jd.model_dump_json(indent=2))

    # --- ISSUE-14/15: ATS scoring + matching --------------------------------
    _print_header("4. ATS scoring & JD<->resume matching (ISSUE-14/15)")
    ats_score, ats_components = calculate_ats_score(raw_text, parsed_resume, parsed_jd)
    match_score, matched, missing, match_components = calculate_match_score(parsed_resume, parsed_jd)
    print(f"ats_score:   {ats_score}  {ats_components}")
    print(f"match_score: {match_score}  {match_components}")
    print(f"matched_skills: {matched}")
    print(f"missing_skills: {missing}")

    # --- ISSUE-16: explainable suggestions ----------------------------------
    _print_header("5. Explainable screening report (ISSUE-16)")
    suggestions = generate_suggestions(parsed_resume, parsed_jd, missing, ats_components)
    for s in suggestions:
        print(f"[{s.impact:>6}] {s.category}: {s.action}")

    async with session_factory() as session:
        session.add(
            AtsReport(
                resume_id=resume_id,
                application_id=application_id,
                ats_score=ats_score,
                match_score=match_score,
                matched_skills=matched,
                missing_skills=missing,
                improvement_suggestions=[s.model_dump() for s in suggestions],
            )
        )
        await session.commit()

    # --- ISSUE-17/18/19: a second, improved version + comparison -----------
    _print_header("6. Resume versioning: upload v2, compare, select best (ISSUE-17/18/19)")
    v2_lines = SAMPLE_RESUME_LINES + [
        "- Deployed services with Docker and AWS ECS",
        "- Automated CI/CD pipelines with GitHub Actions",
    ]
    v2_lines[4] = "Python, React, Git, HTML, CSS, Docker, AWS, CI/CD, FastAPI, PostgreSQL"
    pdf_bytes_v2 = _make_sample_pdf_bytes(v2_lines)
    raw_text_v2 = extract_text_from_pdf(pdf_bytes_v2)
    parsed_resume_v2 = gemini.parse_resume(raw_text_v2)

    resume_id_v2 = new_resume_id()
    async with session_factory() as session:
        resume_v2 = Resume(
            id=resume_id_v2,
            application_id=application_id,
            version_number=2,
            file_url=f"https://storage.example.com/resumes/{resume_id_v2}.pdf",
            raw_text=raw_text_v2,
            parsed_data=parsed_resume_v2.model_dump(),
            is_best_version=False,
        )
        session.add(resume_v2)
        await session.commit()

    ats_score_v2, ats_components_v2 = calculate_ats_score(raw_text_v2, parsed_resume_v2, parsed_jd)
    match_score_v2, matched_v2, missing_v2, _ = calculate_match_score(parsed_resume_v2, parsed_jd)
    print(f"v1: ats={ats_score} match={match_score}")
    print(f"v2: ats={ats_score_v2} match={match_score_v2}")

    class _FakeReport:
        def __init__(self, ats, match):
            self.ats_score = ats
            self.match_score = match

    diff = diff_versions(
        parsed_resume, parsed_resume_v2, _FakeReport(ats_score, match_score),
        _FakeReport(ats_score_v2, match_score_v2),
    )
    recommended, reason = recommend_version(
        diff, _FakeReport(ats_score, match_score), _FakeReport(ats_score_v2, match_score_v2)
    )
    print(f"skills_gained: {diff.skills_gained}")
    print(f"recommended_version: {recommended} — {reason}")

    await engine.dispose()
    _print_header("Done — Module 1 pipeline ran fully standalone.")


if __name__ == "__main__":
    asyncio.run(main())
