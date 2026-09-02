from app.models.application import Application, ApplicationStatus
from app.models.user import Plan, User
from app.core.security import hash_password
from app.db.session import SessionLocal

from tests.test_auth import client


def token_for(email: str, name: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": "correct-horse-battery"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_application_crud_summary_ownership_and_plan_access():
    owner = token_for("owner@example.com", "Owner")
    other = token_for("other@example.com", "Other")
    create = client.post("/api/v1/applications", headers=owner, json={"company": "Acme", "role": "Product Engineer", "status": "APPLIED", "location": "Remote", "job_url": "https://example.com/job"})
    assert create.status_code == 201
    application_id = create.json()["id"]
    assert client.get(f"/api/v1/applications/{application_id}", headers=other).status_code == 404
    assert client.get("/api/v1/applications", headers=owner).json()[0]["company"] == "Acme"
    assert client.patch(f"/api/v1/applications/{application_id}", headers=owner, json={"status": "INTERVIEWING"}).json()["status"] == "INTERVIEWING"
    summary = client.get("/api/v1/dashboard/summary", headers=owner).json()
    assert summary["total"] == 1 and summary["interviewing"] == 1
    assert client.get(f"/api/v1/applications/{application_id}/integrations/ats", headers=owner).status_code == 200
    assert client.get(f"/api/v1/applications/{application_id}/integrations/interviews", headers=owner).status_code == 403
    assert client.delete(f"/api/v1/applications/{application_id}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/applications/{application_id}", headers=owner).status_code == 404


def test_premium_integration_access():
    db = SessionLocal()
    premium = User(name="Premium", email="premium@example.com", password_hash=hash_password("correct-horse-battery"), plan=Plan.PREMIUM)
    application = Application(user=premium, company="Zenith", role="Engineer", status=ApplicationStatus.SAVED)
    db.add_all([premium, application]); db.commit(); db.refresh(application); db.close()
    login = client.post("/api/v1/auth/login", json={"email": "premium@example.com", "password": "correct-horse-battery"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/applications/{application.id}/integrations/interviews", headers=headers).status_code == 200
