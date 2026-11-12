# AI Career Assistant

A career-search workspace built around one idea: everything you see is computed from the two documents
you provide — your resume and the job description.

Free accounts get ATS and role-match scoring with a full, traceable breakdown and one free mock interview.
Premium accounts get the application tracker and a dedicated workspace per role: resume versions, skill gap,
roadmap, what-if simulation, learning resources, and text/audio/video mock interviews with PDF reports.

## Features

### Free tier

- Signup, login, JWT bearer authentication, logout/revocation
- **Quick scan.** Upload a resume and upload or paste a job description, with no application needed. You
  get an ATS score, a role match score, matched and missing skills, and improvement suggestions. Every
  score is broken into named parts with a sentence explaining each part.
- **Free mock interview.** One text-only interview of three questions per free account
  (`FREE_TRIAL_QUESTION_LIMIT`).

### Premium

- **Application tracker.** Company, role, job description, application date and status, each with its own
  workspace. Access is checked against the owner on the server.
- **Resume versions.** Each upload is stored as a version. Versions can be compared, and one can be marked
  as the best.
- **Career intelligence.** Skill gap, prioritised roadmap, learning resources and what-if simulation, all
  computed from the stored ATS report.
- **Mock interviews.** Text, audio or video; technical, friendly, strict, behavioral or mixed personality;
  easy, medium or hard difficulty, adapting from question 3 onward; six questions per session.
  - Questions come from the candidate's own resume. Skills the resume shares with the job description come
    first. A resume project outside the job description is used only when the two share little. The
    interview never asks about a requirement the resume does not show.
  - Audio answers are transcribed with Groq Whisper, falling back to Gemini. Delivery signals (filler
    words, repeated words, hedging, words per minute) are calculated from the transcript.
  - Video interviews sample camera frames and score visible presence: face visible, eye contact,
    engagement and composure. Frames are analysed with Groq vision, falling back to Gemini. No images or
    video are stored.
  - Interview reports show per-question analysis, verbal and visual confidence, and a readiness
    recommendation. A formatted PDF can be downloaded and includes the candidate's name.
- **Billing.** Simulated checkout is the default for local development. Razorpay subscriptions run in TEST
  or LIVE mode with signed verification, reconciliation, cancellation, webhooks and a verified payment
  ledger (`BILLING_MODE=razorpay`).

### Scoring (see [docs/SCORING.md](docs/SCORING.md))

- **ATS score (0–100).** Contact 15, sections 20, JD alignment 15, quantified impact 20, length 15, work
  history 15.
- **Quantified impact.** Achievement statements are read straight from the resume text, from Experience,
  Internships, Projects, Achievements and similar sections. Lines that PDF extraction wrapped are joined
  back together, and bullet glyphs are optional. Dates, years and names such as `Python3` or `EC2` are not
  counted as metrics. Full points are reached when half the statements show a measurable result.
- **Role match (0–100).** `65 × required met + 15 × preferred met + 20 × experience`, where each term is the
  fraction met. Each term is counted in **requirements**, not raw skills. A tier the job description does
  not specify is left out, and the other weights are scaled back up to 100. The response includes a
  numeric breakdown, whose points add up to the score, and a written trace (`match_explanations`), available
  through the API and not shown on screen.
- **Alternative requirements.** The job description may write a requirement as alternatives, such as "Python,
  Go, Java, or Node.js", with any number of options. That counts as one requirement, and every option has equal importance. If the resume
  has none of them, all the options are listed as missing together and share one skill-gap priority. If
  the resume has one, the others are ignored by the score, are not reported as missing, and come last in
  the roadmap with the lowest priority.
- **Reproducible results.** The scoring functions are pure, and every model call that feeds a score runs
  at temperature 0, so the same resume and job description always give the same numbers.

### Platform

- PDF and DOCX text extraction (TXT is also accepted for job descriptions)
- Open-vocabulary skill extraction: technologies outside the built-in taxonomy are still recognised on
  both the resume and the job description
- Gemini structured parsing when configured, with a deterministic offline fallback for parsing, questions
  and evaluation
- The job description used for a scan is saved on its application, so it is restored when the page is
  reopened

## Tech stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS (no charting dependency — visualisations are
  inline SVG)
- Backend: FastAPI, SQLAlchemy, Pydantic Settings, PyJWT, bcrypt
- Data: PostgreSQL for users/applications/payments; configurable async SQLite/PostgreSQL resume store
- Extraction: PyMuPDF and python-docx
- AI (optional): Google Gemini for parsing, questions, evaluation, transcription and vision; Groq for
  transcription and vision, used before Gemini when configured
- PDF reports: server-side generation of interview reports
- Tests: pytest, pytest-asyncio, FastAPI/httpx clients

## Structure

```text
frontend/
  app/                     routes: landing, auth, dashboard (quick scan), upgrade, applications workspace
                           (ATS, versions, skill gap, roadmap, what-if, learning, interviews),
                           free-interview, interview-session, video-interview, career
  components/
    ui/                    button, card, badge, field, alert, empty state, skeleton
    charts/                score gauge, component bars, skill coverage, priority bars, what-if delta
    landing/               marketing sections and the product preview
    workspace/             shared per-application hooks
  lib/                     typed API clients (auth, applications, resumes, quick-scan, billing, career,
                           interviews, free-interview, interview-reports)
backend/
  app/
    api/routes/            auth, billing, access, quick-scan, resumes, applications, career, interviews,
                           free-trial interviews, interview reports
    core/                  configuration and security
    db/                    main and resume database sessions
    models/                user, application, payment, subscription, interview and resume ORM models
    schemas/               API and parsed-data schemas
    services/
      resumes/             extraction, taxonomy, matching, ATS + role-match scoring, storage, versioning,
                           pipeline, Gemini service
      interview_*.py       question generation, evaluation, audio, visual analysis, reporting
      groq_client.py       Groq transcription/vision fallback
      entitlements.py      plan and interview-credit enforcement
      razorpay.py          Razorpay client
  scripts/demo.py          offline end-to-end demo of the resume analyzer
  tests/                   API, resume-flow, scoring, billing, interview, audio/video and PII suites
  alembic/                 migrations
docs/
  SCORING.md               every score formula, with worked examples
  api/API.md               the API contract (routes, access, request/response shapes)
  api/MASTER_API_CONTRACT.md  shared team contract with full JSON examples
  interviews/              audio interview and interview-reporting details
  guides/                  plain-language code explanation and end-to-end internal working
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

For the complete containerized setup, copy `.env.example` to `.env`, then run `docker compose up --build`.
The backend runs migrations before starting. Open the containerized frontend at `http://localhost:3002` and
the API/Swagger UI at `http://localhost:8001/docs`.

## Configuration

Copy `.env.example` to `.env`; never commit `.env`, credentials, databases, uploaded files, or generated caches.

- `DATABASE_URL`: synchronous database for users, applications and payments
- `RESUME_DATABASE_URL`: async database for resume records; defaults to local SQLite for development
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`: token settings
- `BILLING_MODE`: `simulated` for local mock checkout, or `razorpay` for Razorpay test/live checkout
- `FRONTEND_ORIGIN`: allowed browser origin
- `NEXT_PUBLIC_API_URL`: frontend API base URL — the only API base the frontend uses
- `GEMINI_API_KEY`, `GEMINI_MODEL`: optional structured resume/JD parsing, question generation and evaluation
- `GEMINI_TRANSCRIPTION_MODEL`, `GEMINI_VISION_MODEL`: optional audio/vision models (default to `GEMINI_MODEL`)
- `GROQ_API_KEY`, `GROQ_TRANSCRIPTION_MODEL`, `GROQ_VISION_MODEL`: optional Groq transcription/vision, tried first
- `INTERVIEW_AUDIO_MAX_MB`: audio answer upload limit
- `STORAGE_BACKEND`, `STORAGE_LOCAL_DIR`: private local storage or configured provider selection
- `MAX_UPLOAD_MB`: resume/JD upload size limit
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`: matching Razorpay test (`rzp_test_`) or live (`rzp_live_`) credentials
- `RAZORPAY_MONTHLY_PLAN_ID` or `RAZORPAY_PLAN_ID`, `RAZORPAY_YEARLY_PLAN_ID`: provider-created plan IDs
- `RAZORPAY_WEBHOOK_SECRET`: optional secret configured for the public subscription webhook
- `RAZORPAY_MONTHLY_AMOUNT`, `RAZORPAY_MONTHLY_CURRENCY`: expected monthly Premium plan price (₹250 / `25000` paise, `INR`); the Razorpay Dashboard plan must match
- `PRO_MONTHLY_INTERVIEW_CREDITS`, `PRO_YEARLY_INTERVIEW_CREDITS`, `FREE_TRIAL_QUESTION_LIMIT`: entitlement defaults

The default parser works without Gemini. Supabase and Cloudinary adapters are configuration points and must
be completed/configured before use in production.

## API

See **[docs/api/API.md](docs/api/API.md)** for the full contract: every route, its access level, request and
response shapes, and the two response-envelope conventions.

Access levels are enforced server-side from the stored plan, never from anything the client sends:

| Surface | Access |
| --- | --- |
| `/auth`, `/billing` | any authenticated user |
| `/quick-scan` | any authenticated user (the free ATS surface) |
| `/resumes` | any authenticated user, scoped to an owned application |
| `/interviews/free-trial` | any authenticated user (one free text interview) |
| `/applications`, `/dashboard`, `/career`, `/interviews` | Premium only |

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
run `npm run build` before review. Any change to a score must be reflected in `docs/SCORING.md`. Keep migrations, API contracts and frontend types synchronized.

Known limitations:

- Razorpay supports test and live credentials. Public webhook delivery has not been exercised end-to-end.
- Alternative ("X or Y") requirements are recovered from the job description's wording, so a posting
  that implies alternatives without writing them on one line is still scored as separate requirements.
- Quantified impact recognises achievement sections by their heading keywords (Experience, Projects,
  Achievements …); content under an unusual heading is not counted.
- Without Gemini, years of experience are estimated from phrases like "5+ years" and then from
  work-history date ranges; a resume with neither scores 0 on the experience component of the match.
- Alembic migrations target PostgreSQL (they use `now()` and `ALTER TYPE`) and will not run on SQLite.
- Scanned/image-only documents require OCR, which is not included.
