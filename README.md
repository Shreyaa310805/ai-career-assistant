# AI Career Assistant

Authentication-only foundation for the AI-powered resume and interview platform. It provides a Next.js landing/auth flow and a FastAPI/PostgreSQL JWT API. Dashboard product modules are intentionally deferred.

## Run with Docker

1. Copy `.env.example` to `.env` and replace `JWT_SECRET_KEY` and database password.
2. Run `docker compose up --build`.
3. Visit `http://localhost:3000`; API documentation is at `http://localhost:8000/docs`.

Docker runs `alembic upgrade head` before starting the API.

## API

- `POST /api/v1/auth/register` — creates a FREE account and returns an access JWT.
- `POST /api/v1/auth/login` — returns an access JWT.
- `POST /api/v1/auth/logout` — revokes the presented JWT until it expires.
- `GET /api/v1/auth/me` — bearer-token protected profile endpoint.
- `GET /api/v1/access/ats-score` — authenticated; FREE and PREMIUM allowed.
- `GET /api/v1/access/premium` — authenticated; PREMIUM only (returns 403 for FREE).

Future feature routes should depend on `CurrentUser` (ATS) or `PremiumUser` (all other platform tools), defined in `backend/app/api/deps.py`.

## Local development and verification

Use Python 3.12+ and PostgreSQL, set `backend/.env` from its example, then:

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
pytest
```

For the web app:

```bash
cd frontend
npm install
npm run dev
```
