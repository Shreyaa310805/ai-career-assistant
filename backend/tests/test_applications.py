from app.models.application import Application, ApplicationStatus
from app.models.user import Plan, User
from app.core.security import hash_password
from app.db.session import SessionLocal

from tests.test_auth import client


def token_for(email: str, name: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "correct-horse-battery"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def premium_token_for(email: str, name: str) -> dict[str, str]:
    headers = token_for(email, name)
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"}).status_code == 201
    return headers


def test_application_tracker_requires_premium():
    free = token_for("free-tracker@example.com", "Free Tracker")
    assert client.get("/api/v1/applications", headers=free).status_code == 403
    assert client.post("/api/v1/applications", headers=free, json={"company": "Acme", "role": "Engineer"}).status_code == 403
    assert client.get("/api/v1/dashboard/summary", headers=free).status_code == 403


def test_application_crud_summary_ownership_and_plan_access():
    owner = premium_token_for("owner@example.com", "Owner")
    other = premium_token_for("other@example.com", "Other")
    create = client.post("/api/v1/applications", headers=owner, json={"company": "Acme", "role": "Product Engineer", "status": "APPLIED", "location": "Remote", "job_url": "https://example.com/job"})
    assert create.status_code == 201
    application_id = create.json()["id"]
    # Another premium user must not see it: ownership, not plan, decides this.
    assert client.get(f"/api/v1/applications/{application_id}", headers=other).status_code == 404
    assert client.get("/api/v1/applications", headers=owner).json()[0]["company"] == "Acme"
    assert client.patch(f"/api/v1/applications/{application_id}", headers=owner, json={"status": "INTERVIEWING"}).json()["status"] == "INTERVIEWING"
    summary = client.get("/api/v1/dashboard/summary", headers=owner).json()
    assert summary["total"] == 1 and summary["interviewing"] == 1
    assert client.get(f"/api/v1/applications/{application_id}/integrations/ats", headers=owner).status_code == 200
    assert client.delete(f"/api/v1/applications/{application_id}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/applications/{application_id}", headers=owner).status_code == 404


def test_selected_status_is_accepted():
    owner = premium_token_for("selected@example.com", "Selected")
    created = client.post("/api/v1/applications", headers=owner, json={"company": "Zenith", "role": "Engineer", "status": "SELECTED"})
    assert created.status_code == 201
    assert created.json()["status"] == "SELECTED"
    summary = client.get("/api/v1/dashboard/summary", headers=owner).json()
    assert summary["selected"] == 1


def test_premium_integration_access():
    db = SessionLocal()
    premium = User(name="Premium", email="premium@example.com", password_hash=hash_password("correct-horse-battery"), plan=Plan.PREMIUM)
    application = Application(user=premium, company="Zenith", role="Engineer", status=ApplicationStatus.SAVED)
    db.add_all([premium, application]); db.commit(); db.refresh(application); db.close()
    login = client.post("/api/v1/auth/login", json={"email": "premium@example.com", "password": "correct-horse-battery"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/applications/{application.id}/integrations/interviews", headers=headers).status_code == 200


def test_premium_integration_blocked_for_free_plan():
    free = token_for("free-integration@example.com", "Free Integration")
    db = SessionLocal()
    premium = User(name="Other Premium", email="other-premium@example.com", password_hash=hash_password("correct-horse-battery"), plan=Plan.PREMIUM)
    application = Application(user=premium, company="Vertex", role="Engineer", status=ApplicationStatus.SAVED)
    db.add_all([premium, application]); db.commit(); db.refresh(application); db.close()
    assert client.get(f"/api/v1/applications/{application.id}/integrations/interviews", headers=free).status_code == 403
