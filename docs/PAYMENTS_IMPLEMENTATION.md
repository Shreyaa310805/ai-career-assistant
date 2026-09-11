# Payments implementation handoff

Implemented and started locally with Docker Compose. Migration `0008_subscription_allowance` is applied at head. The API health endpoint and both `/upgrade` and `/interview` return HTTP 200. No commit or push was made.

## Validation

- Actual Razorpay TEST monthly plan lookup succeeded: INR 199.00.
- Actual unpaid TEST subscription creation and cancellation succeeded.
- Running PostgreSQL-backed app passed signup, catalog, idempotent trial, report gate, checkout creation/reuse and unpaid cancellation checks.
- Nine billing tests pass, including signed-fixture payment/renewal/cancellation transitions.
- Full Docker suite: 71 passed, 2 pre-existing interview heuristic assertions failed.
- Both failing assertions were reproduced from the original HEAD test definitions against unchanged evaluation code.
- Production frontend build and TypeScript checks passed.
- Person 1, Person 2 and Person 3 master-contract sections were compared with HEAD and remain unchanged.
- Actual hosted Checkout payment success and public webhook delivery have not been exercised in a browser.

Existing failing tests in `backend/tests/test_interviews.py`:

1. `test_fallback_evaluation_links_behavioral_collaboration_components_to_feedback_event` (line 620).
2. `test_fallback_evaluation_handles_friendly_decision_tradeoff_components` (line 658).

The local Python 3.14 environment needed the compatible SQLAlchemy/greenlet pins and restoration of the existing bcrypt pin. Its PDF tests used a newer prebuilt PyMuPDF wheel. Docker uses the project Python 3.12 and pinned PyMuPDF dependency and reproduced the same two baseline failures.

## Migrations

- `0007_subscriptions`: user entitlements, trial flag, subscription/charge/usage tables.
- `0008_subscription_allowance`: paid allowance snapshot and one-open-subscription unique index.

## APIs and UI

All APIs use `/api/v1`:

- `GET /billing/catalog`, `/billing/plan`, `/billing/payments`.
- `POST /billing/checkout`, `/billing/verify`, `/billing/sync`, `/billing/cancel`, `/billing/webhook`.
- `GET` and `POST /practice/interviews`.
- `GET /interviews/{interview_id}/report` with Pro/non-trial/ownership gates.
- Existing interview creation accepts an optional `Idempotency-Key` header; request/response schemas are unchanged.

UI: `/upgrade`, new `/interview`, shared `InterviewPractice` used by the existing application interview page, and Plan & credits / Interview practice navigation.

## Remaining configuration and interactive checks

Open [the local upgrade page](http://localhost:3000/upgrade) and complete the TEST hosted payment flow. Follow [the exact walkthrough](PAYMENTS_TESTING.md#what-to-test-now-without-webhooks) for the trial, 10-to-9 balance, Q2/Q3, report, renewal and cancellation checks.

Webhook setup remains optional locally. Add a public HTTPS `/api/v1/billing/webhook` URL in the TEST dashboard, choose a webhook secret, place it in root `.env`, enable the documented subscription events and recreate the backend. Until then requests return 503 and provider-backed Refresh plan works. See [webhook steps](PAYMENTS_TESTING.md#enable-webhooks-later).

Yearly checkout remains disabled until a real yearly TEST plan ID is configured. Add `RAZORPAY_YEARLY_PLAN_ID` and the chosen yearly allowance, then recreate the backend. No provider ID was invented. See [yearly steps](PAYMENTS_TESTING.md#enable-yearly-checkout-later).

Paid reports currently summarize existing persisted answer evaluations; separate voice/confidence/completion analysis remains outside this payments change.

## Exact files changed or created

| Status | File |
| --- | --- |
| Changed | [.env.example](../.env.example) |
| Changed | [README.md](../README.md) |
| Created | [backend/.dockerignore](../backend/.dockerignore) |
| Changed | [backend/.env.example](../backend/.env.example) |
| Changed | [backend/API.md](../backend/API.md) |
| Created | [backend/alembic/versions/0007_subscriptions.py](../backend/alembic/versions/0007_subscriptions.py) |
| Created | [backend/alembic/versions/0008_subscription_allowance.py](../backend/alembic/versions/0008_subscription_allowance.py) |
| Changed | [backend/app/api/deps.py](../backend/app/api/deps.py) |
| Changed | [backend/app/api/routes/billing.py](../backend/app/api/routes/billing.py) |
| Changed | [backend/app/api/routes/interviews.py](../backend/app/api/routes/interviews.py) |
| Created | [backend/app/api/routes/practice.py](../backend/app/api/routes/practice.py) |
| Changed | [backend/app/core/config.py](../backend/app/core/config.py) |
| Changed | [backend/app/main.py](../backend/app/main.py) |
| Changed | [backend/app/models/__init__.py](../backend/app/models/__init__.py) |
| Changed | [backend/app/models/interview.py](../backend/app/models/interview.py) |
| Changed | [backend/app/models/payment.py](../backend/app/models/payment.py) |
| Created | [backend/app/models/subscription.py](../backend/app/models/subscription.py) |
| Changed | [backend/app/models/user.py](../backend/app/models/user.py) |
| Changed | [backend/app/schemas/billing.py](../backend/app/schemas/billing.py) |
| Created | [backend/app/services/entitlements.py](../backend/app/services/entitlements.py) |
| Created | [backend/app/services/razorpay.py](../backend/app/services/razorpay.py) |
| Changed | [backend/requirements.txt](../backend/requirements.txt) |
| Created | [backend/scripts/check_billing_app.py](../backend/scripts/check_billing_app.py) |
| Created | [backend/scripts/check_razorpay_test.py](../backend/scripts/check_razorpay_test.py) |
| Changed | [backend/tests/conftest.py](../backend/tests/conftest.py) |
| Created | [backend/tests/helpers.py](../backend/tests/helpers.py) |
| Changed | [backend/tests/resumes/conftest.py](../backend/tests/resumes/conftest.py) |
| Changed | [backend/tests/resumes/test_quick_scan.py](../backend/tests/resumes/test_quick_scan.py) |
| Changed | [backend/tests/test_applications.py](../backend/tests/test_applications.py) |
| Changed | [backend/tests/test_billing.py](../backend/tests/test_billing.py) |
| Changed | [docs/MASTER_API_CONTRACT.md](../docs/MASTER_API_CONTRACT.md) |
| Created | [docs/PAYMENTS_IMPLEMENTATION.md](../docs/PAYMENTS_IMPLEMENTATION.md) |
| Created | [docs/PAYMENTS_TESTING.md](../docs/PAYMENTS_TESTING.md) |
| Changed | [frontend/app/applications/[id]/interview/page.tsx](../frontend/app/applications/[id]/interview/page.tsx) |
| Created | [frontend/app/interview/page.tsx](../frontend/app/interview/page.tsx) |
| Changed | [frontend/app/page.tsx](../frontend/app/page.tsx) |
| Changed | [frontend/app/upgrade/page.tsx](../frontend/app/upgrade/page.tsx) |
| Changed | [frontend/components/app-shell.tsx](../frontend/components/app-shell.tsx) |
| Created | [frontend/components/interview-practice.tsx](../frontend/components/interview-practice.tsx) |
| Changed | [frontend/lib/billing.ts](../frontend/lib/billing.ts) |
| Changed | [frontend/lib/interviews.ts](../frontend/lib/interviews.ts) |
