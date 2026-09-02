# Module 1 — Resume & ATS (Person 1)

Standalone backend for the AI-Powered Resume & Job Interview Platform's
Resume & ATS module. Implements ISSUE-10 through ISSUE-19 with **zero
blocking dependencies** on the other three modules: it runs against a
local SQLite file, a local-disk mock file store, and a heuristic resume/JD
parser out of the box, with a real Postgres + Gemini + Supabase/Cloudinary
deployment being a config change away.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # defaults already work with zero setup
uvicorn app.main:app --reload --port 8001
```

Open http://127.0.0.1:8001/docs for interactive Swagger UI, or
http://127.0.0.1:8001/health for a liveness check.

Run the fully standalone, no-server demo (drives the entire pipeline —
upload, parse, score, match, explain, version-compare — with in-memory
sample data):

```bash
python scripts/demo.py
```

Run the test suite:

```bash
pytest -q
```

## What "zero blocking dependency" means here

| Concern | Default (works immediately) | Production swap |
|---|---|---|
| Database | SQLite (`aiosqlite`), file `resume_ats.db` | Set `DATABASE_URL` to Postgres/Supabase (`postgresql+asyncpg://...`) — same models, same code |
| Resume/JD parsing | Deterministic heuristic parser (regex + skills taxonomy) | Set `GEMINI_API_KEY` to route parsing through Gemini structured output |
| File storage | Local disk under `./storage`, fabricated public URL | Set `STORAGE_BACKEND=supabase` or `cloudinary` with credentials |

Every route, model, and schema is identical in both modes — only
`app/config.py` values change. This is what lets Person 1 build and test
this module before Person 4's Postgres instance or a paid Gemini key
exist, per the project brief's "each person builds independently" rule.

## Project layout

```
app/
  main.py              FastAPI app, lifespan startup, global exception handlers
  config.py            Settings (env-driven, safe defaults)
  database.py           Async SQLAlchemy engine/session (SQLite or Postgres)
  models.py             ORM models for resumes / ats_reports (matches ISSUE-03 schema)
  schemas.py             Pydantic v2 request/response/parsed-data schemas
  response.py            {success, data, error} envelope helpers
  exceptions.py           Domain exceptions -> HTTP status + error code mapping
  services/
    extraction.py         ISSUE-10/11/12: PyMuPDF + python-docx text extraction
    storage.py              Mock Supabase/Cloudinary-compatible file storage
    gemini_service.py       ISSUE-13: Gemini structured parsing + heuristic fallback
    taxonomy.py             Shared skills taxonomy/synonym normalization
    matching.py             ISSUE-15: JD<->resume skill matching
    ats_engine.py           ISSUE-14/16: ATS scoring + explainable suggestions
    versioning.py           ISSUE-17/18/19: version numbering, diff, recommendation
  api/v1/resumes.py         All 5 route handlers
tests/                      pytest suite (extraction, scoring, full API lifecycle)
scripts/demo.py              No-server CLI walkthrough of the whole pipeline
frontend/types/resume.types.ts   Copy-paste TypeScript defs for the Next.js team
```

## API contract

All responses use the standard envelope:

```json
{ "success": true, "data": { ... }, "error": null }
{ "success": false, "data": null, "error": { "code": "...", "message": "..." } }
```

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/resumes/upload` | Upload resume (.pdf/.docx), extract text, parse, auto-version |
| POST | `/api/v1/resumes/analyze` | Parse a JD, score ATS/match, return explainable suggestions |
| GET | `/api/v1/resumes/versions/{application_id}` | List all resume versions + their latest ATS report |
| POST | `/api/v1/resumes/compare` | Diff two resume versions and recommend one |
| PATCH | `/api/v1/resumes/select-best` | Flag one version as the best for an application |

See `app/schemas.py` for exact field-level types, and
`frontend/types/resume.types.ts` for the TypeScript mirror.

## Design notes / assumptions

- **UUIDs as strings.** `application_id`, `resume_id`, etc. are validated
  as UUIDs but stored/returned as strings for maximum compatibility across
  SQLite (dev/test) and Postgres (prod).
- **`parsed_data` / `matched_skills` / etc. use a portable JSON type**
  (`app/models.py::PortableJSON`) that renders as native `JSONB` on
  Postgres and falls back to `JSON` on SQLite — same models work in both
  environments without an Alembic migration for local dev.
- **Skill matching is taxonomy-aware.** `app/services/taxonomy.py` maps
  surface forms ("aws", "amazon web services") to one canonical name so
  matching isn't fooled by wording differences between resume and JD.
- **ATS score vs. match score are intentionally independent.** `ats_score`
  reflects resume quality/parseability on its own; `match_score` reflects
  fit against one specific JD. This mirrors the response contract, which
  returns both.
- **First uploaded version defaults to "best"** until a comparison/manual
  selection changes it, so `GET /versions` never returns zero best-flagged
  resumes for an application with at least one version.
- Real deployments should replace the `create_all()` bootstrap in
  `app/database.py::init_db` with Alembic migrations against the frozen
  ISSUE-03 schema; it's kept only for standalone/dev/test convenience.
