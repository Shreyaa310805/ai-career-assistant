"""Pytest fixtures: an isolated in-memory SQLite DB per test (via
StaticPool so the single in-memory connection is shared across the async
test client's requests), sample resume/JD fixtures, and an httpx
AsyncClient wired to the FastAPI app with get_db overridden."""
import io
import uuid

import docx
import fitz
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.resume_session import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session_factory):
    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        registration = await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Resume Tester",
                "email": f"resume-{uuid.uuid4()}@example.com",
                "password": "correct-horse-battery",
            },
        )
        ac.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def application_id(client):
    response = await client.post(
        "/api/v1/applications",
        json={"company": "Test Company", "role": "Software Engineer"},
    )
    assert response.status_code == 201
    return response.json()["id"]


# --------------------------------------------------------------------- #
# Sample fixtures — generated in-process so the test suite has no
# external file dependencies.
# --------------------------------------------------------------------- #
SAMPLE_RESUME_TEXT_LINES = [
    "Jane Doe",
    "jane.doe@example.com | +1 555-123-4567",
    "",
    "Skills",
    "Python, FastAPI, React, PostgreSQL, Git, Docker",
    "",
    "Experience",
    "Software Engineer at Tech Corp",
    "2022 - Present",
    "- Built microservices in FastAPI serving 2M requests/day",
    "- Optimized DB queries, reducing latency by 35%",
    "Junior Developer at StartUpX",
    "2020 - 2022",
    "- Implemented React components for the customer dashboard",
    "",
    "Education",
    "B.S. Computer Science, State University",
]


@pytest.fixture
def sample_resume_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    text = "\n".join(SAMPLE_RESUME_TEXT_LINES)
    page.insert_text((50, 50), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


@pytest.fixture
def sample_resume_docx_bytes() -> bytes:
    document = docx.Document()
    for line in SAMPLE_RESUME_TEXT_LINES:
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_jd_text() -> str:
    return (
        "Senior Backend Developer\n\n"
        "We are looking for a Senior Backend Developer with 5+ years of "
        "experience in Python, FastAPI, Docker, and AWS. PostgreSQL and "
        "CI/CD experience required. Kubernetes is a nice to have.\n\n"
        "Responsibilities:\n"
        "- Design and build scalable REST APIs\n"
        "- Own deployment pipelines\n"
    )
