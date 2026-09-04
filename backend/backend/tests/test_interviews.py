from tests.test_applications import premium_token_for, token_for
from tests.test_auth import client


def create_application(headers: dict[str, str]) -> str:
    response = client.post("/api/v1/applications", headers=headers, json={"company": "Acme", "role": "Engineer"})
    assert response.status_code == 201
    return response.json()["id"]


def test_interview_creation_preserves_contract_and_requires_premium():
    free = token_for("interview-free@example.com", "Interview Free")
    response = client.post(
        "/api/v1/interviews",
        headers=free,
        json={"application_id": "00000000-0000-0000-0000-000000000001", "personality": "technical", "difficulty": "medium"},
    )
    assert response.status_code == 403

    owner = premium_token_for("interview-owner@example.com", "Interview Owner")
    application_id = create_application(owner)
    created = client.post(
        "/api/v1/interviews",
        headers=owner,
        json={"application_id": application_id, "personality": "technical", "difficulty": "medium"},
    )
    assert created.status_code == 200
    assert created.json()["success"] is True
    assert created.json()["error"] is None
    assert created.json()["data"] == {
        "interview_id": created.json()["data"]["interview_id"],
        "application_id": application_id,
        "personality": "technical",
        "difficulty": "medium",
        "status": "created",
        "question_count": 0,
        "started_at": None,
    }


def test_interviews_are_owner_scoped():
    owner = premium_token_for("interview-scope-owner@example.com", "Interview Owner")
    other = premium_token_for("interview-scope-other@example.com", "Interview Other")
    application_id = create_application(owner)
    created = client.post(
        "/api/v1/interviews",
        headers=owner,
        json={"application_id": application_id, "personality": "mixed", "difficulty": "hard"},
    )
    interview_id = created.json()["data"]["interview_id"]
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/interviews/{interview_id}", headers=other).status_code == 404
    assert client.post(
        "/api/v1/interviews",
        headers=other,
        json={"application_id": application_id, "personality": "mixed", "difficulty": "hard"},
    ).status_code == 404
