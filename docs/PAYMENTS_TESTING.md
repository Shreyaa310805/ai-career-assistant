# Payments testing and setup

The app uses Razorpay TEST subscriptions. Existing `PREMIUM` API values are labelled Pro in billing UI.
Prices come from Razorpay plans. Credits and the trial question limit are provisional settings,
not fixed prices or allowances embedded in the frontend.

## Local setup

Use the root `.env` already consumed by Docker Compose. The backend also loads it when launched
locally; an optional `backend/.env` overrides it. Shell/container environment variables take precedence.
Keep real keys out of source files, screenshots, logs and commits. `.env.example` contains placeholders only.

Required for monthly checkout:

- `RAZORPAY_KEY_ID` with the TEST prefix.
- `RAZORPAY_KEY_SECRET`.
- `RAZORPAY_MONTHLY_PLAN_ID`, or the existing fallback `RAZORPAY_PLAN_ID`.

Optional local settings:

- `RAZORPAY_WEBHOOK_SECRET`: absent until public webhook delivery is ready.
- `RAZORPAY_YEARLY_PLAN_ID`: absent until the yearly TEST plan exists.
- `PRO_MONTHLY_INTERVIEW_CREDITS=10`.
- `PRO_YEARLY_INTERVIEW_CREDITS=120` (per paid annual period, not monthly).
- `FREE_TRIAL_QUESTION_LIMIT=3`.

The monthly/yearly allowance is snapshotted on each verified paid cycle. Changing its configuration
affects the next cycle. Changing the trial limit affects subsequent trial question requests.
Only `rzp_test_` credentials are accepted by the provider service.

From the repository root:

```powershell
docker compose up -d --build
```

The backend startup runs `alembic upgrade head`. New revisions are `0007_subscriptions` and
`0008_subscription_allowance`; existing data is retained. Existing one-time Premium accounts
retain their access and receive an initial monthly credit allowance. Use a newly registered Free
account to test the full trial/upgrade lifecycle.

## What to test now, without webhooks

1. Open `http://localhost:3000/signup`, create a Free account, then open `/interview`.
2. Start the lifetime trial and generate/answer questions 1, 2, and 3.
3. A fourth question and another trial start return `403`. Session history allows resumption.
4. View premium report: blocked. Trial sessions never receive a final report, even after upgrading.
5. Open `/upgrade`. The actual configured monthly plan price appears. Yearly is unavailable while
   its provider plan is absent.
6. Open monthly Razorpay TEST Checkout. Use the current official Razorpay subscription TEST payment
   details and choose the successful simulated bank outcome. Do not use real card details.
7. The callback is posted to `/api/v1/billing/verify`. It must match the stored owned subscription,
   captured payment and paid invoice before Pro activates. An authorization-only payment is pending.
8. If capture lags, or the callback is interrupted, select **Refresh plan**. This calls
   `/billing/sync`, which independently checks Razorpay, and does not need a webhook secret.
9. Pro shows 10/10 with default monthly settings. Start a new Pro interview: 9/10. Q2, Q3,
   answer submission, evaluation and report reads must remain 9/10.
10. The paid-session report displays persisted answer evaluations and their overall average.
    This integration does not add the separate Person 2 voice/confidence/completion algorithms.
11. Trigger a subsequent TEST charge using Razorpay's subscription testing controls. Refresh plan
    to reconcile the verified increased paid count: balance resets to 10/10, without rollover.
12. Cancel renewal in `/upgrade`. Pro remains active through the paid period and repeated cancel
    requests have no extra effect. Provider cancellation or period expiry removes Pro access.
    The lifetime trial remains consumed.

Razorpay's hosted payment modal and simulated bank step require an interactive browser. The
provider smoke script below checks actual plan lookup, subscription creation and unpaid cancellation;
it does not claim to complete Checkout or a real provider renewal.

## Automated validation

From `backend` in the project Python environment:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_billing.py -q
..\.venv\Scripts\python.exe -m pytest -q
```

Tests clear developer API credentials and use isolated databases. Billing fixtures simulate captured
payments and signed webhooks, covering trial limits, report gates, one debit per start, idempotent
start retries, ownership, bad signatures, renewal resets, replay safety, configurable values,
expiry, optional yearly/webhook configuration, reconciliation and cancellation.

The database/row-lock environment is PostgreSQL via Docker. The unit API tests use SQLite;
PostgreSQL row-lock behavior is not established solely by SQLite test results.

From `frontend`: `npm.cmd run build` (Windows) or `npm run build`.

Optional actual provider smoke check, from `backend`:

```powershell
..\.venv\Scripts\python.exe scripts/check_razorpay_test.py
..\.venv\Scripts\python.exe scripts/check_razorpay_test.py --create-and-cancel
```

The second command creates a disposable unpaid TEST subscription and immediately cancels it.
It prints only safe status/price metadata, never credentials or raw provider responses.
It does not change application user entitlements.

## Enable webhooks later

1. Expose the backend through a public HTTPS deployment or tunnel.
2. In the Razorpay TEST dashboard create a webhook for:
   `https://YOUR_PUBLIC_HOST/api/v1/billing/webhook`.
3. Choose an independent webhook secret and put the same value in root `.env` as
   `RAZORPAY_WEBHOOK_SECRET`. Recreate the backend with
   `docker compose up -d --force-recreate backend` so environment changes take effect.
4. Subscribe to `subscription.charged`, `subscription.cancelled`, `subscription.completed`,
   `subscription.pending`, `subscription.halted`, `subscription.activated`, and
   `subscription.authenticated`.
5. Run a successful TEST payment and TEST renewal. Confirm successful webhook deliveries and
   automatic credit reset without selecting Refresh plan. Retry a delivery after spending one
   credit and confirm the spent balance is unchanged.
6. Test failed/pending payment and cancellation. Pending/halted events do not grant credits;
   already paid access expires at its stored end time.

Until the secret exists the webhook returns `503`, with no trusted event processing. A configured
secret never permits unsigned events: invalid signatures return `400`. There is no public
simulate-payment, force-Pro or reset-credits endpoint.

## Enable yearly checkout later

Create a Razorpay TEST plan with `period=yearly`, `interval=1`, and the team's chosen price/currency.
Set its real ID as `RAZORPAY_YEARLY_PLAN_ID`, set the provisional yearly allowance, and recreate
the backend. The catalog/UI will expose the actual yearly price automatically. Test activation,
annual reset and cancellation using that plan. Do not add an invented yearly ID to placeholders.
Active plan switching/proration is outside this implementation; cancel the current subscription
before purchasing a different interval after its paid period ends.

## References

- [Razorpay subscription integration and callback signatures](https://razorpay.com/docs/payments/subscriptions/integration-guide/)
- [Official subscription TEST payment and renewal instructions](https://razorpay.com/docs/payments/subscriptions/test/)
- [Webhook signature validation](https://razorpay.com/docs/webhooks/validate-test/)
- [Subscription webhook events](https://razorpay.com/docs/webhooks/subscriptions/)
- [Fetch subscription invoices](https://razorpay.com/docs/api/payments/subscriptions/fetch-invoices/)
- [Master API contract, section 20](MASTER_API_CONTRACT.md#20-person-4---payments--subscriptions--entitlements)
