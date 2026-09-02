"""End-to-end coverage of the five contract endpoints, chained the way a
real client would use them: upload -> upload v2 -> analyze both ->
list versions -> compare -> select-best."""
import uuid

import pytest


async def test_full_resume_lifecycle(client, sample_resume_pdf_bytes, sample_resume_docx_bytes, sample_jd_text):
    application_id = str(uuid.uuid4())

    # --- Upload v1 (PDF) ---------------------------------------------------
    resp = await client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume_v1.pdf", sample_resume_pdf_bytes, "application/pdf")},
        data={"application_id": application_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None
    v1 = body["data"]
    assert v1["version_number"] == 1
    assert v1["application_id"] == application_id
    assert v1["parsed_data"]["email"] == "jane.doe@example.com"
    assert "Python" in v1["parsed_data"]["skills"]
    resume_id_v1 = v1["resume_id"]

    # --- Upload v2 (DOCX) for the same application -------------------------
    resp = await client.post(
        "/api/v1/resumes/upload",
        files={
            "file": (
                "resume_v2.docx",
                sample_resume_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"application_id": application_id},
    )
    assert resp.status_code == 200, resp.text
    v2 = resp.json()["data"]
    assert v2["version_number"] == 2
    resume_id_v2 = v2["resume_id"]

    # --- Analyze v1 against a JD -------------------------------------------
    resp = await client.post(
        "/api/v1/resumes/analyze",
        json={
            "application_id": application_id,
            "resume_id": resume_id_v1,
            "jd_text": sample_jd_text,
        },
    )
    assert resp.status_code == 200, resp.text
    analysis = resp.json()["data"]
    assert analysis["resume_id"] == resume_id_v1
    assert 0 <= analysis["ats_score"] <= 100
    assert 0 <= analysis["match_score"] <= 100
    assert isinstance(analysis["matched_skills"], list)
    assert isinstance(analysis["missing_skills"], list)
    assert len(analysis["improvement_suggestions"]) >= 1
    assert analysis["improvement_suggestions"][0]["impact"] in ("High", "Medium", "Low")

    # --- Analyze v2 too, so compare() has scores for both versions --------
    resp = await client.post(
        "/api/v1/resumes/analyze",
        json={
            "application_id": application_id,
            "resume_id": resume_id_v2,
            "jd_text": sample_jd_text,
        },
    )
    assert resp.status_code == 200, resp.text

    # --- List versions -------------------------------------------------------
    resp = await client.get(f"/api/v1/resumes/versions/{application_id}")
    assert resp.status_code == 200, resp.text
    versions = resp.json()["data"]["versions"]
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2
    assert versions[0]["latest_ats_report"] is not None

    # --- Compare v1 vs v2 ------------------------------------------------
    resp = await client.post(
        "/api/v1/resumes/compare",
        json={"resume_id_v1": resume_id_v1, "resume_id_v2": resume_id_v2},
    )
    assert resp.status_code == 200, resp.text
    comparison = resp.json()["data"]
    assert comparison["recommended_version"] in ("v1", "v2", "tie")
    assert "diff" in comparison

    # --- Select best version -----------------------------------------------
    resp = await client.patch(
        "/api/v1/resumes/select-best",
        json={"application_id": application_id, "best_resume_id": resume_id_v2},
    )
    assert resp.status_code == 200, resp.text
    best = resp.json()["data"]
    assert best["best_resume_id"] == resume_id_v2
    assert best["updated_versions"] == 2

    # verify only v2 is flagged best now
    resp = await client.get(f"/api/v1/resumes/versions/{application_id}")
    versions = resp.json()["data"]["versions"]
    flags = {v["version_number"]: v["is_best_version"] for v in versions}
    assert flags == {1: False, 2: True}


async def test_upload_rejects_unsupported_file_type(client):
    resp = await client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
        data={"application_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


async def test_upload_rejects_invalid_application_id(client, sample_resume_pdf_bytes):
    resp = await client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
        data={"application_id": "not-a-uuid"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_analyze_returns_404_for_unknown_resume(client, sample_jd_text):
    resp = await client.post(
        "/api/v1/resumes/analyze",
        json={
            "application_id": str(uuid.uuid4()),
            "resume_id": str(uuid.uuid4()),
            "jd_text": sample_jd_text,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESUME_NOT_FOUND"


async def test_analyze_rejects_mismatched_application(client, sample_resume_pdf_bytes, sample_jd_text):
    application_id = str(uuid.uuid4())
    other_application_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
        data={"application_id": application_id},
    )
    resume_id = resp.json()["data"]["resume_id"]

    resp = await client.post(
        "/api/v1/resumes/analyze",
        json={
            "application_id": other_application_id,
            "resume_id": resume_id,
            "jd_text": sample_jd_text,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "APPLICATION_MISMATCH"


async def test_versions_empty_list_for_unknown_application(client):
    resp = await client.get(f"/api/v1/resumes/versions/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json()["data"]["versions"] == []


async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
