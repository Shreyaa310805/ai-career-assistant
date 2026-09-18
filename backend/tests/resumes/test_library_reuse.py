"""Additive endpoints: GET /resumes/library and POST /resumes/reuse."""
import uuid

import pytest

from app.db.resume_session import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


async def _upload(client, application_id, pdf_bytes):
    response = await client.post(
        "/api/v1/resumes/upload",
        data={"application_id": application_id},
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _new_application(client, company, role):
    response = await client.post("/api/v1/applications", json={"company": company, "role": role})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_library_is_empty_without_resumes(client):
    response = await client.get("/api/v1/resumes/library")
    assert response.status_code == 200
    assert response.json()["data"] == {"resumes": []}


@pytest.mark.asyncio
async def test_library_lists_resumes_labeled_by_company_and_role(
    client, application_id, sample_resume_pdf_bytes
):
    uploaded = await _upload(client, application_id, sample_resume_pdf_bytes)

    items = (await client.get("/api/v1/resumes/library")).json()["data"]["resumes"]
    assert len(items) == 1
    item = items[0]
    assert item["resume_id"] == uploaded["resume_id"]
    assert item["company"] == "Test Company"
    assert item["role"] == "Software Engineer"
    assert item["label"] == "Test Company — Software Engineer"
    assert item["is_quick_scan"] is False
    assert "Python" in item["skills"]


@pytest.mark.asyncio
async def test_library_includes_quick_scans_across_applications(
    client, application_id, sample_resume_pdf_bytes
):
    await _upload(client, application_id, sample_resume_pdf_bytes)
    quick = await client.post(
        "/api/v1/quick-scan/resume",
        files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
    )
    assert quick.status_code == 200

    items = (await client.get("/api/v1/resumes/library")).json()["data"]["resumes"]
    assert len(items) == 2
    quick_items = [i for i in items if i["is_quick_scan"]]
    assert [i["label"] for i in quick_items] == ["Quick scan"]
    assert quick_items[0]["resume_id"] == quick.json()["data"]["resume_id"]


@pytest.mark.asyncio
async def test_library_never_exposes_contact_details_or_storage_paths(
    client, application_id, sample_resume_pdf_bytes
):
    await _upload(client, application_id, sample_resume_pdf_bytes)
    body = (await client.get("/api/v1/resumes/library")).text
    assert "jane.doe@example.com" not in body
    assert "555-123-4567" not in body
    assert "local://" not in body


@pytest.mark.asyncio
async def test_reuse_clones_resume_into_new_application_as_version_one(
    client, application_id, sample_resume_pdf_bytes
):
    source = await _upload(client, application_id, sample_resume_pdf_bytes)
    # Give the source a higher version so we can see the count is not inherited.
    second = await _upload(client, application_id, sample_resume_pdf_bytes)
    assert second["version_number"] == 2

    target = await _new_application(client, "Acme", "Backend Dev")
    response = await client.post(
        "/api/v1/resumes/reuse",
        json={"source_resume_id": second["resume_id"], "application_id": target},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["application_id"] == target
    assert data["version_number"] == 1
    assert data["resume_id"] not in (source["resume_id"], second["resume_id"])
    assert data["parsed_data"]["skills"] == second["parsed_data"]["skills"]

    versions = (await client.get(f"/api/v1/resumes/versions/{target}")).json()["data"]["versions"]
    assert [v["version_number"] for v in versions] == [1]
    assert versions[0]["is_best_version"] is True
    assert versions[0]["latest_ats_report"] is None


@pytest.mark.asyncio
async def test_reused_resume_can_be_analyzed_in_target_application(
    client, application_id, sample_resume_pdf_bytes, sample_jd_text
):
    source = await _upload(client, application_id, sample_resume_pdf_bytes)
    target = await _new_application(client, "Acme", "Backend Dev")
    reused = (
        await client.post(
            "/api/v1/resumes/reuse",
            json={"source_resume_id": source["resume_id"], "application_id": target},
        )
    ).json()["data"]

    analyze = await client.post(
        "/api/v1/resumes/analyze",
        data={
            "application_id": target,
            "resume_id": reused["resume_id"],
            "jd_text": sample_jd_text,
        },
    )
    assert analyze.status_code == 200, analyze.text
    assert analyze.json()["data"]["ats_explanations"]["contact_completeness"]


@pytest.mark.asyncio
async def test_reuse_appends_version_when_target_already_has_resumes(
    client, application_id, sample_resume_pdf_bytes
):
    source = await _upload(client, application_id, sample_resume_pdf_bytes)
    target = await _new_application(client, "Acme", "Backend Dev")
    await _upload(client, target, sample_resume_pdf_bytes)

    response = await client.post(
        "/api/v1/resumes/reuse",
        json={"source_resume_id": source["resume_id"], "application_id": target},
    )
    assert response.json()["data"]["version_number"] == 2


@pytest.mark.asyncio
async def test_reuse_from_quick_scan_resume(client, sample_resume_pdf_bytes):
    quick = (
        await client.post(
            "/api/v1/quick-scan/resume",
            files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
        )
    ).json()["data"]
    target = await _new_application(client, "Acme", "Backend Dev")

    response = await client.post(
        "/api/v1/resumes/reuse",
        json={"source_resume_id": quick["resume_id"], "application_id": target},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["version_number"] == 1


@pytest.mark.asyncio
async def test_reuse_rejects_unknown_source_and_bad_ids(client, application_id):
    missing = await client.post(
        "/api/v1/resumes/reuse",
        json={"source_resume_id": str(uuid.uuid4()), "application_id": application_id},
    )
    assert missing.status_code == 404

    invalid = await client.post(
        "/api/v1/resumes/reuse",
        json={"source_resume_id": "not-a-uuid", "application_id": application_id},
    )
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_other_users_cannot_see_or_reuse_a_resume(
    client, application_id, sample_resume_pdf_bytes, db_session_factory
):
    source = await _upload(client, application_id, sample_resume_pdf_bytes)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        registration = await other.post(
            "/api/v1/auth/register",
            json={
                "name": "Other User",
                "email": f"other-{uuid.uuid4()}@example.com",
                "password": "correct-horse-battery",
            },
        )
        other.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
        await other.post("/api/v1/billing/checkout", json={"plan": "PREMIUM"})
        other_app = await _new_application(other, "Rival", "Spy")

        library = (await other.get("/api/v1/resumes/library")).json()["data"]["resumes"]
        assert library == []

        stolen = await other.post(
            "/api/v1/resumes/reuse",
            json={"source_resume_id": source["resume_id"], "application_id": other_app},
        )
        assert stolen.status_code == 404
