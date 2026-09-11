"""Check configured TEST integration without printing credentials or raw provider responses.

From backend: python scripts/check_razorpay_test.py [--create-and-cancel]
The optional flag creates an unauthenticated TEST subscription and cancels it immediately.
It never attempts a payment and never changes a local user's entitlements.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.core.config import get_settings
from app.services.razorpay import api


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-and-cancel", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    plan_id = settings.provider_plan_id("monthly")
    try:
        plan = api("GET", f"plans/{plan_id}")
        if plan.get("period") != "monthly" or plan.get("interval") != 1:
            raise HTTPException(503, "Configured plan is not monthly with interval 1")
        print("Monthly TEST plan verified.")
        print("Price (minor units):", plan["item"]["amount"], plan["item"]["currency"])
        print("Yearly plan configured:", bool(settings.provider_plan_id("yearly")))
        print("Webhook secret configured:", bool(settings.razorpay_webhook_secret))
        if args.create_and_cancel:
            sub = api("POST", "subscriptions", {"plan_id": plan_id, "total_count": 2,
                "quantity": 1, "customer_notify": 0, "notes": {"purpose": "SkillSync TEST integration smoke check"}})
            print("TEST subscription created:", sub["status"])
            cancelled = api("POST", f"subscriptions/{sub['id']}/cancel", {"cancel_at_cycle_end": 0})
            print("TEST subscription cancellation:", cancelled["status"])
    except HTTPException as exc:
        print(f"Integration check failed ({exc.status_code}): {exc.detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
