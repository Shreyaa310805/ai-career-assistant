from tests.test_auth import client
from tests.test_applications import token_for


def test_checkout_upgrades_plan_and_unlocks_premium_routes():
    headers = token_for("billing-upgrade@example.com", "Billing Upgrade")
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "FREE"
    assert client.get("/api/v1/applications", headers=headers).status_code == 403

    checkout = client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"})
    assert checkout.status_code == 201
    body = checkout.json()
    assert body["already_premium"] is False
    assert body["user"]["plan"] == "PREMIUM"
    assert body["payment"]["status"] == "SUCCEEDED"
    assert body["payment"]["provider"] == "mock"
    assert body["payment"]["amount_cents"] == 1900

    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "PREMIUM"
    assert client.get("/api/v1/applications", headers=headers).status_code == 200


def test_checkout_is_idempotent_and_does_not_double_charge():
    headers = token_for("billing-idempotent@example.com", "Billing Idempotent")
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"}).status_code == 201
    repeat = client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "PREMIUM"})
    assert repeat.status_code == 201
    assert repeat.json()["already_premium"] is True
    assert repeat.json()["payment"] is None

    plan = client.get("/api/v1/billing/plan", headers=headers).json()
    assert plan["plan"] == "PREMIUM"
    assert len(plan["payments"]) == 1
    assert plan["premium_since"] is not None


def test_checkout_rejects_buying_the_free_plan():
    headers = token_for("billing-free@example.com", "Billing Free")
    assert client.post("/api/v1/billing/checkout", headers=headers, json={"plan": "FREE"}).status_code == 422
    assert client.get("/api/v1/auth/me", headers=headers).json()["plan"] == "FREE"


def test_billing_requires_authentication():
    assert client.get("/api/v1/billing/plan").status_code == 401
    assert client.post("/api/v1/billing/checkout", json={"plan": "PREMIUM"}).status_code == 401
