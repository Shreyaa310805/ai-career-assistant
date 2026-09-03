"""FREE-tier quick scan: the ATS pipeline without an application tracker."""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.resume_session import get_db
from app.main import app


@pytest_asyncio.fixture
async def free_client(db_session_factory):
    """An authenticated client that stays on the FREE plan."""

    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        registration = await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Free Scanner",
                "email": f"free-{uuid.uuid4()}@example.com",
                "password": "correct-horse-battery",
            },
        )
        ac.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
        yield ac
    app.dependency_overrides.clear()


async def _upload(client, pdf_bytes):
    return await client.post(
        "/api/v1/quick-scan/resume",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )


@pytest.mark.asyncio
async def test_free_user_can_scan_without_an_application(free_client, sample_resume_pdf_bytes, sample_jd_text):
    # The tracker is closed to this account.
    assert (await free_client.get("/api/v1/applications")).status_code == 403

    upload = await _upload(free_client, sample_resume_pdf_bytes)
    assert upload.status_code == 200, upload.text
    upload_data = upload.json()["data"]
    assert upload_data["version_number"] == 1
    assert upload_data["parsed_data"]["skills"]

    analyze = await free_client.post(
        "/api/v1/quick-scan/analyze",
        data={"resume_id": upload_data["resume_id"], "jd_text": sample_jd_text},
    )
    assert analyze.status_code == 200, analyze.text
    data = analyze.json()["data"]
    assert 0 <= data["ats_score"] <= 100
    assert 0 <= data["match_score"] <= 100
    assert data["matched_skills"]
    assert data["ats_breakdown"]["section_coverage"] >= 0
    assert "required_skill_match_pct" in data["match_breakdown"]


@pytest.mark.asyncio
async def test_latest_returns_the_most_recent_scan(free_client, sample_resume_pdf_bytes, sample_jd_text):
    empty = await free_client.get("/api/v1/quick-scan/latest")
    assert empty.status_code == 200
    assert empty.json()["data"] == {"resume": None, "report": None}

    upload_data = (await _upload(free_client, sample_resume_pdf_bytes)).json()["data"]
    await free_client.post(
        "/api/v1/quick-scan/analyze",
        data={"resume_id": upload_data["resume_id"], "jd_text": sample_jd_text},
    )

    latest = (await free_client.get("/api/v1/quick-scan/latest")).json()["data"]
    assert latest["resume"]["resume_id"] == upload_data["resume_id"]
    assert latest["report"]["ats_score"] > 0
    assert latest["report"]["ats_breakdown"]


@pytest.mark.asyncio
async def test_scratch_application_stays_hidden_after_upgrading(free_client, sample_resume_pdf_bytes):
    await _upload(free_client, sample_resume_pdf_bytes)
    assert (await free_client.post("/api/v1/billing/checkout", json={"plan": "PREMIUM"})).status_code == 201

    listed = await free_client.get("/api/v1/applications")
    assert listed.status_code == 200
    assert listed.json() == []

    summary = (await free_client.get("/api/v1/dashboard/summary")).json()
    assert summary["total"] == 0


@pytest.mark.asyncio
async def test_cannot_analyze_another_users_resume(free_client, client, sample_resume_pdf_bytes, sample_jd_text):
    """`client` is a different, premium account sharing the resume database."""
    victim_upload = (await _upload(client, sample_resume_pdf_bytes)).json()["data"]

    stolen = await free_client.post(
        "/api/v1/quick-scan/analyze",
        data={"resume_id": victim_upload["resume_id"], "jd_text": sample_jd_text},
    )
    assert stolen.status_code == 400
    assert stolen.json()["success"] is False


@pytest.mark.asyncio
async def test_quick_scan_requires_authentication(db_session_factory, sample_resume_pdf_bytes):
    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/quick-scan/resume",
            files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 401
    app.dependency_overrides.clear()
