import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models.payment import Payment
from app.models.user import User
from app.db.session import SessionLocal
from tests.test_applications import token_for
from tests.test_auth import client


@pytest.fixture
def razorpay_provider(monkeypatch):
    settings = get_settings()
    for name, value in {
        "razorpay_key_id": "rzp_test_fixture",
        "razorpay_key_secret": "checkout-secret",
        "razorpay_webhook_secret": "webhook-secret",
        "razorpay_plan_id": "plan_monthly_fixture",
        "razorpay_monthly_plan_id": "",
        "razorpay_yearly_plan_id": "",
        "pro_monthly_interview_credits": 10,
    }.items():
        monkeypatch.setattr(settings, name, value)
    state = {
        "id": "sub_" + uuid.uuid4().hex,
        "plan_id": "plan_monthly_fixture",
        "status": "created",
        "paid_count": 0,
        "current_end": int(time.time()) + 30 * 86400,
    }
    payment = {
        "id": "pay_" + uuid.uuid4().hex,
        "status": "captured",
        "invoice_id": "inv_" + uuid.uuid4().hex,
        "amount": 19900,
        "currency": "INR",
    }
    calls = []

    def api(method, path, payload=None):
        calls.append((method, path, payload))
        if path.startswith("plans/"):
            period = "yearly" if path.endswith("yearly") else "monthly"
            return {"period": period, "interval": 1, "item": {"amount": 19900, "currency": "INR"}}
        if path == "subscriptions":
            return {**state}
        if path.startswith("subscriptions/") and path.endswith("/cancel"):
            if not payload or not payload.get("cancel_at_cycle_end"):
                state["status"] = "cancelled"
            return {**state}
        if path.startswith("subscriptions/"):
            return {**state}
        if path.startswith("payments/"):
            return {**payment}
        if path.startswith("invoices/"):
            return {"subscription_id": state["id"], "payment_id": payment["id"], "status": "paid"}
        if path.startswith("invoices?"):
            return {"items": [{"status": "paid", "payment_id": payment["id"], "paid_at": int(time.time())}]}
        raise AssertionError(f"Unexpected provider request {method} {path}")

    monkeypatch.setattr("app.services.razorpay.api", api)
    return state, payment, calls


def signed_verification(state, payment, secret=b"checkout-secret"):
    signature = hmac.new(secret, f"{payment['id']}|{state['id']}".encode(), hashlib.sha256).hexdigest()
    return {
        "razorpay_subscription_id": state["id"],
        "razorpay_payment_id": payment["id"],
        "razorpay_signature": signature,
    }


def signed_webhook(state, payment, event="subscription.charged"):
    body = json.dumps({
        "event": event,
        "payload": {
            "subscription": {"entity": state},
            "payment": {"entity": payment},
        },
    }).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    return client.post("/api/v1/billing/webhook", content=body, headers={"x-razorpay-signature": signature})


def start_checkout(headers):
    return client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"})


def test_checkout_creates_and_reuses_provider_subscription_without_granting_access(razorpay_provider):
    state, _, calls = razorpay_provider
    headers = token_for("billing-checkout@example.com", "Billing Checkout")

    first = start_checkout(headers)
    assert first.status_code == 201
    assert first.json()["subscription_id"] == state["id"]
    assert first.json()["key_id"] == "rzp_test_fixture"
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "FREE"

    again = start_checkout(headers)
    assert again.status_code == 201
    assert again.json()["subscription_id"] == state["id"]
    assert sum(method == "POST" and path == "subscriptions" for method, path, _ in calls) == 1


def test_verification_requires_owned_subscription_captured_payment_and_paid_invoice(razorpay_provider):
    state, payment, _ = razorpay_provider
    headers = token_for("billing-verify@example.com", "Billing Verify")
    other = token_for("billing-other@example.com", "Billing Other")
    assert start_checkout(headers).status_code == 201

    valid = signed_verification(state, payment)
    assert client.post("/api/v1/billing/verify", headers=other, json=valid).status_code == 404
    forged = {**valid, "razorpay_signature": "0" * 64}
    assert client.post("/api/v1/billing/verify", headers=headers, json=forged).status_code == 400

    payment["status"] = "authorized"
    assert client.post("/api/v1/billing/verify", headers=headers, json=valid).status_code == 409
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "FREE"

    payment["status"] = "captured"
    state.update(status="active", paid_count=1)
    verified = client.post("/api/v1/billing/verify", headers=headers, json=valid)
    assert verified.status_code == 200
    assert verified.json()["plan"] == "PREMIUM"
    assert verified.json()["credits"] == 10
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "PREMIUM"

    # Retrying the same verified callback is idempotent in the local payment ledger.
    assert client.post("/api/v1/billing/verify", headers=headers, json=valid).status_code == 200
    with SessionLocal() as db:
        assert db.query(Payment).filter(Payment.provider == "razorpay").count() == 1


def test_webhook_signature_payment_idempotency_and_subscription_cancellation(razorpay_provider):
    state, payment, _ = razorpay_provider
    headers = token_for("billing-webhook@example.com", "Billing Webhook")
    assert start_checkout(headers).status_code == 201

    invalid = client.post("/api/v1/billing/webhook", content=b"{}", headers={"x-razorpay-signature": "0" * 64})
    assert invalid.status_code == 400
    state.update(status="active", paid_count=1)
    assert signed_webhook(state, payment).status_code == 200
    assert signed_webhook(state, payment).status_code == 200
    assert len(client.get("/api/v1/billing/payments", headers=headers).json()) == 1

    cancelled = client.post("/api/v1/billing/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["plan"] == "PREMIUM"
    assert cancelled.json()["cancel_at_cycle_end"] is True
    assert client.post("/api/v1/billing/cancel", headers=headers).status_code == 200
    assert sum(path.endswith("/cancel") for _, path, _ in razorpay_provider[2]) == 1

    state["status"] = "cancelled"
    assert signed_webhook(state, payment, "subscription.cancelled").status_code == 200
    result = client.get("/api/v1/billing/plan", headers=headers)
    assert result.status_code == 200
    assert result.json()["plan"] == "FREE"
    assert result.json()["credits"] == 0


def test_checkout_requires_auth_valid_plan_and_test_provider_configuration(monkeypatch):
    headers = token_for("billing-config@example.com", "Billing Config")
    monkeypatch.setattr(get_settings(), "razorpay_key_id", "")

    assert client.get("/api/v1/billing/plan").status_code == 401
    assert client.post("/api/v1/billing/checkout", json={}).status_code == 401
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "FREE"}).status_code == 422
    assert start_checkout(headers).status_code == 503


def test_catalog_only_exposes_configured_provider_plans(razorpay_provider, monkeypatch):
    headers = token_for("billing-catalog@example.com", "Billing Catalog")
    catalog = client.get("/api/v1/billing/catalog", headers=headers)
    assert catalog.status_code == 200
    plans = catalog.json()["plans"]
    assert plans[0]["available"] is True
    assert plans[0]["amount"] == 19900
    assert plans[1]["available"] is False

    monkeypatch.setattr(get_settings(), "razorpay_yearly_plan_id", "plan_yearly")
    yearly = client.get("/api/v1/billing/catalog", headers=headers).json()["plans"][1]
    assert yearly["available"] is True


def test_expired_subscription_access_is_removed_on_authenticated_request(razorpay_provider):
    state, payment, _ = razorpay_provider
    headers = token_for("billing-expiry@example.com", "Billing Expiry")
    assert start_checkout(headers).status_code == 201
    state.update(status="active", paid_count=1)
    assert client.post(
        "/api/v1/billing/verify", headers=headers, json=signed_verification(state, payment)
    ).json()["plan"] == "PREMIUM"
    user_id = uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["id"])
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.pro_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    expired = client.get("/api/v1/auth/me", headers=headers)
    assert expired.status_code == 200
    assert expired.json()["plan"] == "FREE"
    with SessionLocal() as db:
        assert db.get(User, user_id).interview_credits == 0
