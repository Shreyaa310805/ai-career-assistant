import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-long-enough-for-development-only"

from fastapi.testclient import TestClient  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
import app.models  # noqa: E402,F401
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_complete_auth_flow_and_plan_guards():
    registration = client.post("/api/v1/auth/register", json={"name": "Ada Lovelace", "email": "ada@example.com", "password": "correct-horse-battery"})
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["email"] == "ada@example.com"
    assert client.get("/api/v1/access/ats-score", headers=headers).status_code == 200
    assert client.get("/api/v1/access/premium", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "correct-horse-battery"})
    assert login.status_code == 200


def test_registration_validation_and_duplicate_email():
    assert client.post("/api/v1/auth/register", json={"name": "X", "email": "bad", "password": "short"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"name": "Ada", "email": "ADA@example.com", "password": "correct-horse-battery"}).status_code == 409
