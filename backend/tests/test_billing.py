import hashlib
import hmac
import json
import time
import uuid
import pytest
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User
from tests.test_auth import client
from tests.test_applications import token_for
from tests.test_interviews import fake_evaluator


@pytest.fixture
def provider(monkeypatch):
    settings = get_settings()
    for name, value in {"razorpay_key_id": "rzp_test_fixture", "razorpay_key_secret": "fixture-secret",
                        "razorpay_plan_id": "plan_fixture", "razorpay_monthly_plan_id": "", "razorpay_yearly_plan_id": "",
                        "razorpay_webhook_secret": "webhook-secret", "pro_monthly_interview_credits": 10,
                        "free_trial_question_limit": 3}.items():
        monkeypatch.setattr(settings, name, value)
    state = {"id": "sub_" + uuid.uuid4().hex, "plan_id": "plan_fixture", "status": "created", "paid_count": 0,
             "current_end": int(time.time()) + 86400 * 30}
    payment = {"id": "pay_" + uuid.uuid4().hex, "status": "captured", "invoice_id": "inv_fixture", "amount": 190000, "currency": "INR"}
    calls = []
    def api(method, path, payload=None):
        calls.append((method, path, payload))
        if path.startswith("plans/"):
            return {"period": "yearly" if path.endswith("plan_yearly") else "monthly", "interval": 1,
                    "item": {"amount": 190000, "currency": "INR"}}
        if path.startswith("payments/"): return dict(payment)
        if path.startswith("invoices?"):
            return {"items": [{"status": "paid", "payment_id": payment["id"], "created_at": int(time.time())}]}
        if path.startswith("invoices/"):
            return {"subscription_id": state["id"], "payment_id": payment["id"], "status": "paid"}
        return dict(state)
    monkeypatch.setattr("app.services.razorpay.api", api)
    return state, payment, calls


def signed_verification(state, payment):
    signature = hmac.new(b"fixture-secret", f"{payment['id']}|{state['id']}".encode(), hashlib.sha256).hexdigest()
    return {"razorpay_subscription_id": state["id"], "razorpay_payment_id": payment["id"], "razorpay_signature": signature}


def webhook(state, payment, event="subscription.charged"):
    raw = json.dumps({"event": event, "payload": {"subscription": {"entity": state}, "payment": {"entity": payment}}}).encode()
    signature = hmac.new(b"webhook-secret", raw, hashlib.sha256).hexdigest()
    return client.post("/api/v1/billing/webhook", content=raw, headers={"x-razorpay-signature": signature})


def practice(headers):
    return client.post("/api/v1/practice/interviews", headers=headers, json={"personality": "technical", "difficulty": "medium"})


def test_full_trial_subscription_credit_renewal_cancellation_lifecycle(provider, monkeypatch):
    from app.schemas.interview import DifficultyEnum, GeneratedQuestion
    async def question(**kw):
        return GeneratedQuestion(question=f"Explain your approach to Python problem number {kw['question_number']}?",
            topic="Python", question_type="technical", difficulty=DifficultyEnum.medium, expected_skills=["Python"], reason="Practice question")
    monkeypatch.setattr("app.api.routes.interviews.generate_question_for_application", question)
    monkeypatch.setattr("app.services.interview_evaluation.get_gemini_service", lambda: fake_evaluator())
    headers = token_for("lifecycle@example.com", "Lifecycle")
    state, payment, calls = provider
    plan = lambda: client.get("/api/v1/billing/plan", headers=headers).json()
    trial = practice(headers).json()["data"]["interview_id"]
    assert not plan()["trial_available"]
    assert practice(headers).status_code == 403
    for n in range(1, 4):
        response = client.post(f"/api/v1/interviews/{trial}/questions", headers=headers, json={})
        assert response.status_code == 200
        assert response.json()["data"]["question_number"] == n
    assert client.post(f"/api/v1/interviews/{trial}/questions", headers=headers, json={}).status_code == 403
    assert client.get(f"/api/v1/interviews/{trial}/report", headers=headers).status_code == 403
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"}).status_code == 201
    assert plan()["plan"] == "FREE"
    assert client.post("/api/v1/billing/checkout", headers=headers, json={}).json()["subscription_id"] == state["id"]
    assert sum(method == "POST" and path == "subscriptions" for method, path, _ in calls) == 1
    state.update(status="active", paid_count=1)
    assert client.post("/api/v1/billing/verify", headers=headers, json=signed_verification(state, payment)).status_code == 200
    assert plan()["credits"] == 10
    assert client.get(f"/api/v1/interviews/{trial}/report", headers=headers).status_code == 403
    session = practice(headers).json()["data"]["interview_id"]
    assert plan()["credits"] == 9
    for _ in range(3):
        q = client.post(f"/api/v1/interviews/{session}/questions", headers=headers, json={}).json()["data"]
        assert plan()["credits"] == 9
    answer = client.post(f"/api/v1/interviews/{session}/answers", headers=headers,
        json={"question_id": q["question_id"], "answer_text": "I validate the Python input and test boundary conditions", "source": "typed"}).json()["data"]
    assert client.post(f"/api/v1/interviews/{session}/answers/{answer['answer_id']}/evaluate", headers=headers).status_code == 200
    report = client.get(f"/api/v1/interviews/{session}/report", headers=headers)
    assert report.status_code == 200 and report.json()["data"]["overall_score"] == 78
    assert webhook(state, payment).status_code == 200
    assert client.post("/api/v1/billing/verify", headers=headers, json=signed_verification(state, payment)).status_code == 200
    assert plan()["credits"] == 9
    state.update(paid_count=2, current_end=state["current_end"] + 86400 * 30)
    payment["id"] = "pay_" + uuid.uuid4().hex
    assert webhook(state, payment).status_code == 200
    assert plan()["credits"] == 10
    assert practice(headers).status_code == 200
    assert webhook(state, payment).status_code == 200
    assert plan()["credits"] == 9
    assert client.post("/api/v1/billing/cancel", headers=headers).status_code == 200
    assert plan()["cancel_at_cycle_end"] and plan()["plan"] == "PREMIUM"
    assert client.post("/api/v1/billing/cancel", headers=headers).status_code == 200
    assert sum(path.endswith("/cancel") for _, path, _ in calls) == 1
    state["status"] = "cancelled"
    assert webhook(state, payment, "subscription.cancelled").status_code == 200
    assert plan()["plan"] == "FREE" and plan()["credits"] == 0
    assert webhook(state, payment).status_code == 200
    assert plan()["plan"] == "FREE"
    assert len(client.get("/api/v1/billing/payments", headers=headers).json()) == 2
    assert client.get(f"/api/v1/interviews/{session}/report", headers=headers).status_code == 403
    assert practice(headers).status_code == 403


def test_verification_rejects_forgery_wrong_owner_and_uncaptured_payment(provider):
    state, payment, _ = provider
    headers = token_for("secure-billing@example.com", "Secure Billing")
    other = token_for("other-billing@example.com", "Other Billing")
    assert client.post("/api/v1/billing/checkout", headers=headers, json={}).status_code == 201
    payload = signed_verification(state, payment)
    assert client.post("/api/v1/billing/verify", headers=other, json=payload).status_code == 404
    assert client.post("/api/v1/billing/verify", headers=headers, json={**payload, "razorpay_signature": "0" * 64}).status_code == 400
    assert client.post("/api/v1/billing/webhook", content=b"{}").status_code == 400
    payment["status"] = "authorized"
    assert client.post("/api/v1/billing/verify", headers=headers, json=payload).status_code == 409
    assert client.get("/api/v1/billing/plan", headers=headers).json()["plan"] == "FREE"


def test_expiry_and_credit_exhaustion():
    from datetime import datetime, timedelta, timezone
    from tests.test_applications import premium_token_for
    headers = premium_token_for("exhausted@example.com", "Exhausted")
    user_id = uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["id"])
    for _ in range(10): assert practice(headers).status_code == 200
    assert practice(headers).status_code == 403
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.pro_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "FREE"


def test_checkout_requires_config_and_auth(monkeypatch):
    headers = token_for("unconfigured@example.com", "Unconfigured")
    monkeypatch.setattr(get_settings(), "razorpay_key_id", "")
    assert client.post("/api/v1/billing/checkout", headers=headers, json={}).status_code == 503
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "FREE"}).status_code == 422
    assert client.get("/api/v1/billing/plan").status_code == 401
    assert client.post("/api/v1/billing/checkout", json={}).status_code == 401


def test_optional_webhook_and_yearly_configuration(provider, monkeypatch):
    headers = token_for('optional-billing@example.com', 'Optional Billing')
    monkeypatch.setattr(get_settings(), 'razorpay_webhook_secret', '')
    assert client.post('/api/v1/billing/webhook', content=b'{}').status_code == 503
    catalog = client.get('/api/v1/billing/catalog', headers=headers).json()
    assert catalog['plans'][0]['available'] is True
    assert catalog['plans'][1]['available'] is False
    assert client.post('/api/v1/billing/checkout', headers=headers, json={'interval': 'yearly'}).status_code == 503
    assert client.post('/api/v1/billing/checkout', headers=headers, json={'interval': 'weekly'}).status_code == 422


def test_paid_start_idempotency_history_and_report_ownership():
    from tests.test_applications import premium_token_for
    headers = premium_token_for('start-idempotency@example.com', 'Start Idempotency')
    other = premium_token_for('report-owner@example.com', 'Report Owner')
    request_headers = {**headers, 'Idempotency-Key': str(uuid.uuid4())}
    first = practice(request_headers)
    assert first.status_code == 200
    assert practice(request_headers).json()['data']['interview_id'] == first.json()['data']['interview_id']
    assert client.get('/api/v1/billing/plan', headers=headers).json()['credits'] == 9
    history = client.get('/api/v1/practice/interviews', headers=headers).json()['data']
    assert len(history) == 1 and history[0]['credits_charged'] == 1
    assert client.get(f"/api/v1/interviews/{first.json()['data']['interview_id']}/report", headers=other).status_code == 404
    changed = client.post('/api/v1/practice/interviews', headers=request_headers, json={'personality': 'friendly'})
    assert changed.status_code == 409


def test_reconcile_without_webhook_recovers_capture_and_renewal(provider):
    state, payment, _ = provider
    headers = token_for('reconcile@example.com', 'Reconcile Billing')
    assert client.post('/api/v1/billing/checkout', headers=headers, json={}).status_code == 201
    state.update(status='active', paid_count=1)
    assert client.post('/api/v1/billing/sync', headers=headers).json()['credits'] == 10
    assert practice(headers).status_code == 200
    assert client.post('/api/v1/billing/sync', headers=headers).json()['credits'] == 9
    state.update(paid_count=2, current_end=state['current_end'] + 86400 * 30)
    payment['id'] = 'pay_' + uuid.uuid4().hex
    assert client.post('/api/v1/billing/sync', headers=headers).json()['credits'] == 10


def test_configurable_credits_and_trial_limit(provider, monkeypatch):
    from app.schemas.interview import DifficultyEnum, GeneratedQuestion
    monkeypatch.setattr(get_settings(), 'pro_monthly_interview_credits', 7)
    monkeypatch.setattr(get_settings(), 'free_trial_question_limit', 1)
    async def question(**kwargs):
        return GeneratedQuestion(question='Explain a Python design decision?', topic='Python', question_type='technical',
            difficulty=DifficultyEnum.medium, expected_skills=[], reason='Configurable trial test')
    monkeypatch.setattr('app.api.routes.interviews.generate_question_for_application', question)
    headers = token_for('configured-limits@example.com', 'Configured Limits')
    session = practice(headers).json()['data']['interview_id']
    assert client.post(f'/api/v1/interviews/{session}/questions', headers=headers, json={}).status_code == 200
    assert client.post(f'/api/v1/interviews/{session}/questions', headers=headers, json={}).status_code == 403
    state, payment, _ = provider
    client.post('/api/v1/billing/checkout', headers=headers, json={})
    state.update(status='active', paid_count=1)
    assert client.post('/api/v1/billing/verify', headers=headers, json=signed_verification(state, payment)).json()['credits'] == 7


def test_yearly_configuration_uses_real_selected_plan_and_allowance(provider, monkeypatch):
    state, payment, calls = provider
    monkeypatch.setattr(get_settings(), 'razorpay_yearly_plan_id', 'plan_yearly')
    monkeypatch.setattr(get_settings(), 'pro_yearly_interview_credits', 80)
    state.update(plan_id='plan_yearly', current_end=int(time.time()) + 86400 * 365)
    headers = token_for('yearly-fixture@example.com', 'Yearly Fixture')
    assert client.get('/api/v1/billing/catalog', headers=headers).json()['plans'][1]['available']
    assert client.post('/api/v1/billing/checkout', headers=headers, json={'interval': 'yearly'}).status_code == 201
    assert next(payload for method, path, payload in calls if method == 'POST' and path == 'subscriptions')['plan_id'] == 'plan_yearly'
    state.update(status='active', paid_count=1)
    result = client.post('/api/v1/billing/verify', headers=headers, json=signed_verification(state, payment)).json()
    assert result['interval'] == 'yearly' and result['credits'] == result['credit_limit'] == 80
    monkeypatch.setattr(get_settings(), 'pro_yearly_interview_credits', 60)
    assert client.get('/api/v1/billing/plan', headers=headers).json()['credit_limit'] == 80
