# AI Career Assistant

AI Career Assistant is a career-search workspace for authenticated users. It combines a job-application tracker with an application-scoped resume workflow: upload a PDF/DOCX resume, extract structured career details, parse a job description, and calculate an explainable ATS and skill-match score.

## Features

- Signup, login, JWT bearer authentication, logout/revocation, and account plans
- Ownership-protected application tracker and dashboard summary
- Private resume upload and local/server storage abstraction
- PDF and DOCX text extraction (TXT is also accepted for job descriptions)
- Gemini structured parsing when configured, with deterministic offline fallback
- ATS quality scoring, JD skill matching, missing skills, and improvement suggestions
- Resume version storage and retrieval

Resume comparison/recommendation is intentionally outside this integration scope and remains owned by another developer.

## Tech stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Pydantic Settings, PyJWT
- Data: PostgreSQL for users/applications; configurable async SQLite/PostgreSQL resume store
- Extraction: PyMuPDF and python-docx
- Optional parsing: Google Gemini
- Tests: pytest, pytest-asyncio, FastAPI/httpx clients

## Structure

```text
frontend/                  Next.js application and API client helpers
backend/
  app/
    api/routes/            auth, applications, access, and resume endpoints
    core/                   shared application configuration and security
    db/                     main and resume database sessions
    models/                 user, application, and resume ORM models
    schemas/                API and parsed-data schemas
    services/resumes/      extraction, storage, parsing, matching, and ATS logic
  tests/                    main API tests and authenticated resume integration tests
  alembic/                  main application migrations
  scripts/                  optional development/demo utilities
docker-compose.yml          PostgreSQL, backend, and frontend services
```

## Local setup

Use Python 3.12+ and Node.js 20+. From the repository root:

```bash
cp .env.example .env
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
pytest -q
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The API and Swagger UI are at `http://localhost:8000` and `/docs`.

For the complete containerized setup, run `docker compose up --build`. The backend runs migrations before starting.

## Configuration

Copy `.env.example` to `.env`; never commit `.env`, credentials, databases, uploaded files, or generated caches.

- `DATABASE_URL`: synchronous database for users/applications
- `RESUME_DATABASE_URL`: async database for resume records; defaults to local SQLite for development
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`: token settings
- `FRONTEND_ORIGIN`: allowed browser origin
- `NEXT_PUBLIC_API_URL`: frontend API base URL
- `GEMINI_API_KEY`, `GEMINI_MODEL`: optional structured resume/JD parsing
- `STORAGE_BACKEND`, `STORAGE_LOCAL_DIR`: private local storage or configured provider selection
- `MAX_UPLOAD_MB`: resume/JD upload size limit

The default parser works without Gemini. Supabase and Cloudinary adapters are configuration points and must be completed/configured before use in production.

## API

All endpoints below use the `/api/v1` prefix. Resume endpoints require a bearer token and an application owned by the current user.

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET/POST /applications`, `GET/PATCH/DELETE /applications/{application_id}`
- `GET /dashboard/summary`
- `POST /resumes/upload` — multipart PDF/DOCX upload, extraction, parsing, and versioning
- `POST /resumes/analyze` — multipart resume/application/JD input, ATS scoring, matching, and JD extraction
- `GET /resumes/versions/{application_id}` — owned resume versions and latest reports
- `GET /applications/{application_id}/integrations/ats`

Resume responses use `{success, data, error}`. Main auth/application responses use their direct response schemas.

## Development workflow and limitations

Make focused changes in the relevant route/service/schema layer, add or update tests, run `pytest -q`, and run `npm run build` before review. Keep migrations, API contracts, and frontend types synchronized. Local file storage is private filesystem storage, not a public download endpoint; production deployments should use a durable private object store. Scanned/image-only documents require OCR, which is not currently included.
