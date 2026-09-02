"""Nothing that identifies the candidate, and no server-side storage path,
may leave through an API response.

The resume record deliberately holds `candidate_name`, `email`, `phone`,
`raw_text` and a private `file_url`. These assertions are the guard that keeps
them server-side as new endpoints are added.
"""
import json

import pytest

FORBIDDEN_SUBSTRINGS = (
    "jane.doe@example.com",   # extracted from the sample resume
    "555-123-4567",           # extracted phone number
    "candidate_name",
    "raw_text",
    "storage/",
    ".pdf",
    ".docx",
)


def assert_clean(response, label: str) -> dict:
    body = response.text
    lowered = body.lower()
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle.lower() not in lowered, f"{label} leaked {needle!r}"
    return json.loads(body)


@pytest.mark.asyncio
async def test_resume_endpoints_never_expose_identity_or_paths(
    client, application_id, sample_resume_pdf_bytes, sample_jd_text
):
    upload = await client.post(
        "/api/v1/resumes/upload",
        files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
        data={"application_id": application_id},
    )
    assert upload.status_code == 200
    resume_id = assert_clean(upload, "upload")["data"]["resume_id"]

    analyze = await client.post(
        "/api/v1/resumes/analyze",
        data={"application_id": application_id, "resume_id": resume_id, "jd_text": sample_jd_text},
    )
    assert analyze.status_code == 200
    assert_clean(analyze, "analyze")

    versions = await client.get(f"/api/v1/resumes/versions/{application_id}")
    assert versions.status_code == 200
    data = assert_clean(versions, "versions")["data"]

    # The locator is present but opaque: no filesystem path, no extension.
    file_url = data["versions"][0]["file_url"]
    assert file_url == f"resume://{resume_id}"


@pytest.mark.asyncio
async def test_quick_scan_endpoints_never_expose_identity_or_paths(
    client, sample_resume_pdf_bytes, sample_jd_text
):
    upload = await client.post(
        "/api/v1/quick-scan/resume",
        files={"file": ("resume.pdf", sample_resume_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 200
    resume_id = assert_clean(upload, "quick-scan upload")["data"]["resume_id"]

    analyze = await client.post(
        "/api/v1/quick-scan/analyze",
        data={"resume_id": resume_id, "jd_text": sample_jd_text},
    )
    assert analyze.status_code == 200
    assert_clean(analyze, "quick-scan analyze")

    latest = await client.get("/api/v1/quick-scan/latest")
    assert latest.status_code == 200
    assert_clean(latest, "quick-scan latest")
