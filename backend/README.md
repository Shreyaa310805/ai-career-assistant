# AI Career Assistant

A career-search workspace built around one idea: everything you see is computed from the two documents
you provide — your resume and the job description.

Free accounts get real ATS scoring with a full breakdown. Premium accounts get the application tracker
and a dedicated workspace per role: resume versions, skill gap, roadmap, what-if simulation and learning.

## Features

- Signup, login, JWT bearer authentication, logout/revocation
- **Free tier** — resume upload, job-description upload or paste, ATS score with its six named
  sub-components, skill matching and improvement suggestions, with no application required
- **Simulated upgrade to Premium** — a mock checkout that flips the account server-side. No card data is
  requested, transmitted or stored
- **Premium** — ownership-protected application tracker (company, role, job description, application date,
  status), a per-application workspace, and career intelligence derived from stored ATS reports
- PDF and DOCX text extraction (TXT also accepted for job descriptions)
- Open-vocabulary skill extraction: technologies outside the built-in taxonomy are still recognised on
  both the resume and the JD
- Gemini structured parsing when configured, with a deterministic offline fallback
- Resume version storage, comparison and best-version selection

Interview preparation is not implemented; it appears in the UI as a clearly marked "Coming Soon" placeholder.

## Tech stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS (no charting dependency — visualisations are
  inline SVG)
- Backend: FastAPI, SQLAlchemy, Pydantic Settings, PyJWT, bcrypt
- Data: PostgreSQL for users/applications/payments; configurable async SQLite/PostgreSQL resume store
- Extraction: PyMuPDF and python-docx
- Optional parsing: Google Gemini
- Tests: pytest, pytest-asyncio, FastAPI/httpx clients

## Structure

```text
frontend/
  app/                     routes: landing, auth, dashboard, upgrade, applications workspace
  components/
    ui/                    button, card, badge, field, alert, empty state, skeleton
    charts/                score gauge, component bars, skill coverage, priority bars, what-if delta
    landing/               marketing sections and the product preview
    workspace/             shared per-application hooks
  lib/                     typed API clients (auth, applications, resumes, quick-scan, billing, career)
backend/
  app/
    api/routes/            auth, billing, quick-scan, resumes, applications, career, access
    core/                  configuration and security
    db/                    main and resume database sessions
    models/                user, application, payment, resume ORM models
    schemas/               API and parsed-data schemas
    services/resumes/      extraction, taxonomy, matching, ATS scoring, storage, versioning, pipeline
  tests/                   API, resume-flow, billing, quick-scan and PII-protection suites
  alembic/                 migrations
  API.md                   the API contract
docker-compose.yml         PostgreSQL, backend and frontend services
```

## Local setup

Use Python 3.12+ and Node.js 20+. From the repository root:

```bash
cp .env.example .env
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head          # requires PostgreSQL; the migrations are Postgres-specific
pytest -q
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The API and Swagger UI are at `http://localhost:8000` and `/docs`.

For the complete containerized setup, run `docker compose up --build`. The backend runs migrations before
starting.

## Configuration

Copy `.env.example` to `.env`; never commit `.env`, credentials, databases, uploaded files, or generated caches.

- `DATABASE_URL`: synchronous database for users, applications and payments
- `RESUME_DATABASE_URL`: async database for resume records; defaults to local SQLite for development
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`: token settings
- `FRONTEND_ORIGIN`: allowed browser origin
- `NEXT_PUBLIC_API_URL`: frontend API base URL — the only API base the frontend uses
- `GEMINI_API_KEY`, `GEMINI_MODEL`: optional structured resume/JD parsing
- `STORAGE_BACKEND`, `STORAGE_LOCAL_DIR`: private local storage or configured provider selection
- `MAX_UPLOAD_MB`: resume/JD upload size limit

The default parser works without Gemini. Supabase and Cloudinary adapters are configuration points and must
be completed/configured before use in production.

## API

See **[backend/API.md](backend/API.md)** for the full contract: every route, its access level, request and
response shapes, and the two response-envelope conventions.

Access levels are enforced server-side from the stored plan, never from anything the client sends:

| Surface | Access |
| --- | --- |
| `/auth`, `/billing` | any authenticated user |
| `/quick-scan` | any authenticated user (the free ATS surface) |
| `/resumes` | any authenticated user, scoped to an owned application |
| `/applications`, `/dashboard`, `/career` | Premium only |

> The `/resumes/*` contract is frozen. Its shared implementation lives in
> `app/services/resumes/pipeline.py` so other surfaces can reuse the pipeline without changing those routes.

## Privacy

Identity data extracted from a resume — name, email address, phone number — and the raw resume text are
stored server-side and never returned by any endpoint. `public_resume_details()` in
`app/services/resumes/pipeline.py` is the single projection every response passes through, and
`tests/resumes/test_pii_protection.py` asserts no route leaks them. Uploaded files live in private storage
with no download endpoint; version summaries carry an opaque `resume://<resume_id>` reference rather than a
storage path.

## Development workflow and limitations

Make focused changes in the relevant route/service/schema layer, add or update tests, run `pytest -q`, and
run `npm run build` before review. Keep migrations, API contracts and frontend types synchronized.

Known limitations:

- Payments are simulated. `backend/app/api/routes/billing.py` records a mock transaction; wiring a real
  processor means replacing that handler's body, not the route or its schema.
- Interview preparation is not implemented.
- Years of experience are estimated by regex over phrases like "5+ years", so a resume that never states a
  total will score 0 on the experience component of the match.
- Alembic migrations target PostgreSQL (they use `now()` and `ALTER TYPE`) and will not run on SQLite.
- Scanned/image-only documents require OCR, which is not included.
