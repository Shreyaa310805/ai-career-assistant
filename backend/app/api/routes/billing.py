"""Razorpay subscription checkout, verification, reconciliation, and history."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionCharge
from app.models.user import Plan, User
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PaymentResponse, PlanResponse
from app.services import razorpay
from app.services.entitlements import expire_access, lock_user

router = APIRouter(prefix="/billing", tags=["billing"])
TERMINAL_STATUSES = {"cancelled", "completed", "expired"}


def latest_subscription(db, user_id):
    return db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status.notin_(TERMINAL_STATUSES))
        .order_by(Subscription.id.desc())
    )


def plan_data(db, user: User):
    user = expire_access(db, user)
    subscription = latest_subscription(db, user.id)
    settings = get_settings()
    payments = db.scalars(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.asc())
    ).all()
    successful = [payment for payment in payments if payment.status == PaymentStatus.SUCCEEDED]
    return {
        "plan": user.plan,
        "premium_since": successful[0].created_at if successful else None,
        "payments": payments,
        "credits": user.interview_credits if user.plan == Plan.PREMIUM else 0,
        "credit_limit": subscription.credit_limit if subscription and subscription.credit_limit else settings.interview_allowance(subscription.interval if subscription else "monthly"),
        "trial_available": not user.trial_used,
        "trial_question_limit": settings.free_trial_question_limit,
        "interval": subscription.interval if subscription else "monthly",
        "pro_until": user.pro_until,
        "subscription_id": subscription.id if subscription else None,
        "subscription_status": subscription.status if subscription else None,
        "cancel_at_cycle_end": subscription.cancel_at_cycle_end if subscription else False,
        "webhook_configured": bool(settings.razorpay_webhook_secret),
        "test_mode": True,
        "configured": razorpay.configured(),
    }


@router.get("/catalog")
def catalog(current_user: CurrentUser):
    settings = get_settings()
    plans = []
    for interval in ("monthly", "yearly"):
        plan_id = settings.provider_plan_id(interval)
        available = bool(plan_id) and razorpay.configured()
        item = {"interval": interval, "available": available, "credits": settings.interview_allowance(interval), "amount": None, "currency": None}
        if available:
            entity = razorpay.api("GET", f"plans/{plan_id}")
            if entity.get("period") != interval or entity.get("interval") != 1:
                item["available"] = False
            else:
                item.update(amount=entity["item"]["amount"], currency=entity["item"]["currency"])
        plans.append(item)
    return {"plans": plans, "trial_question_limit": settings.free_trial_question_limit}


@router.get("/plan", response_model=PlanResponse)
def get_plan(db: DbSession, current_user: CurrentUser):
    return plan_data(db, current_user)


@router.get("/payments", response_model=list[PaymentResponse])
def payment_history(db: DbSession, current_user: CurrentUser):
    return db.scalars(
        select(Payment).where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc()).limit(100)
    ).all()


@router.post("/checkout", status_code=201, response_model=CheckoutResponse, response_model_exclude_none=True)
def checkout(payload: CheckoutRequest, db: DbSession, current_user: CurrentUser):
    if payload.plan != Plan.PREMIUM:
        raise HTTPException(422, "Only PREMIUM can be purchased")
    user = lock_user(db, current_user.id)
    user = expire_access(db, user)
    if user.plan == Plan.PREMIUM:
        return {"already_premium": True}

    settings = get_settings()
    plan_id = settings.provider_plan_id(payload.interval)
    if not plan_id:
        raise HTTPException(503, "This billing interval is not configured yet")
    plan = razorpay.api("GET", f"plans/{plan_id}")
    if plan.get("period") != payload.interval or plan.get("interval") != 1:
        raise HTTPException(503, "The Razorpay plan billing interval does not match configuration")

    subscription = latest_subscription(db, user.id)
    if subscription:
        provider_state = razorpay.api("GET", f"subscriptions/{subscription.id}")
        if provider_state.get("status") in TERMINAL_STATUSES:
            sync_subscription(db, subscription, provider_state)
            user = lock_user(db, user.id)
            subscription = latest_subscription(db, user.id)
    if subscription and subscription.plan_id != plan_id:
        raise HTTPException(409, "An unfinished subscription exists for another billing interval. Cancel it first.")
    if subscription is None:
        entity = razorpay.api("POST", "subscriptions", {
            "plan_id": plan_id,
            "total_count": 120 if payload.interval == "monthly" else 10,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {"user_id": str(user.id)},
        })
        if entity.get("plan_id") != plan_id or not entity.get("id", "").startswith("sub_"):
            raise HTTPException(502, "Razorpay returned an invalid subscription")
        subscription = Subscription(id=entity["id"], user_id=user.id, plan_id=plan_id, interval=payload.interval)
        db.add(subscription)
        db.commit()
    return {
        "already_premium": False,
        "key_id": settings.razorpay_key_id,
        "subscription_id": subscription.id,
        "amount": plan["item"]["amount"],
        "currency": plan["item"]["currency"],
    }


def sync_subscription(db, subscription: Subscription, entity: dict, payment: dict | None = None):
    user = lock_user(db, subscription.user_id)
    db.refresh(subscription)
    if entity.get("id") != subscription.id or entity.get("plan_id") != subscription.plan_id:
        raise HTTPException(400, "Subscription does not match the purchased plan")
    state = entity.get("status")
    paid_count = int(entity.get("paid_count") or 0)
    if payment is not None:
        if payment.get("status") != "captured" or not payment.get("invoice_id"):
            raise HTTPException(409, "Payment is not captured yet; wait for confirmation")
        invoice = razorpay.api("GET", f"invoices/{payment['invoice_id']}")
        if invoice.get("subscription_id") != subscription.id or invoice.get("payment_id") != payment.get("id") or invoice.get("status") != "paid":
            raise HTTPException(400, "Payment does not belong to this subscription")
        if not db.get(SubscriptionCharge, payment["id"]):
            db.add(SubscriptionCharge(payment_id=payment["id"], subscription_id=subscription.id))
            db.add(Payment(
                user_id=user.id,
                plan=Plan.PREMIUM,
                amount_cents=payment["amount"],
                currency=payment["currency"],
                provider="razorpay",
                status=PaymentStatus.SUCCEEDED,
            ))
        if paid_count > subscription.paid_count and state in {"active", "pending", "halted"}:
            current_end = entity.get("current_end")
            if not current_end:
                raise HTTPException(409, "Waiting for the subscription billing period")
            user.pro_until = datetime.fromtimestamp(current_end, timezone.utc)
            if user.pro_until > datetime.now(timezone.utc):
                user.plan = Plan.PREMIUM
                user.interview_credits = get_settings().interview_allowance(subscription.interval)
                subscription.credit_limit = user.interview_credits
            subscription.paid_count = paid_count

    subscription.status = state or subscription.status
    if subscription.status in TERMINAL_STATUSES:
        subscription.cancel_at_cycle_end = False
        other_open = db.scalar(select(Subscription.id).where(
            Subscription.user_id == user.id,
            Subscription.id != subscription.id,
            Subscription.status.notin_(TERMINAL_STATUSES),
        ))
        if other_open is None:
            user.plan = Plan.FREE
            user.interview_credits = 0
            user.pro_until = datetime.now(timezone.utc)
    db.commit()
    return plan_data(db, user)


class Verification(BaseModel):
    razorpay_subscription_id: str = Field(pattern=r"^sub_[A-Za-z0-9]+$")
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$")
    razorpay_signature: str = Field(min_length=64, max_length=64)


@router.post("/verify", response_model=PlanResponse)
def verify(payload: Verification, db: DbSession, current_user: CurrentUser):
    subscription = db.get(Subscription, payload.razorpay_subscription_id)
    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(404, "Subscription not found")
    razorpay.verify_signature(
        f"{payload.razorpay_payment_id}|{subscription.id}".encode(),
        payload.razorpay_signature,
        get_settings().razorpay_key_secret,
    )
    entity = razorpay.api("GET", f"subscriptions/{subscription.id}")
    payment = razorpay.api("GET", f"payments/{payload.razorpay_payment_id}")
    return sync_subscription(db, subscription, entity, payment)


@router.post("/webhook")
async def webhook(request: Request, db: DbSession):
    secret = get_settings().razorpay_webhook_secret
    if not secret:
        raise HTTPException(503, "Webhook verification is not configured")
    raw = await request.body()
    razorpay.verify_signature(raw, request.headers.get("x-razorpay-signature", ""), secret)
    try:
        event = json.loads(raw)
        event_type = event["event"]
        subscription_id = event["payload"]["subscription"]["entity"]["id"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Malformed webhook")
    if event_type not in {
        "subscription.charged", "subscription.cancelled", "subscription.completed",
        "subscription.halted", "subscription.pending", "subscription.activated",
        "subscription.authenticated",
    }:
        return {"received": True}
    subscription = db.get(Subscription, subscription_id)
    if subscription:
        entity = razorpay.api("GET", f"subscriptions/{subscription.id}")
        payment = None
        if event_type == "subscription.charged":
            event_payment = event["payload"].get("payment", {}).get("entity", {})
            payment_id = event_payment.get("id")
            if not payment_id:
                raise HTTPException(400, "Malformed charged event")
            payment = razorpay.api("GET", f"payments/{payment_id}")
        sync_subscription(db, subscription, entity, payment)
    return {"received": True}


@router.post("/cancel", response_model=PlanResponse)
def cancel(db: DbSession, current_user: CurrentUser):
    user = lock_user(db, current_user.id)
    subscription = latest_subscription(db, user.id)
    if subscription and not subscription.cancel_at_cycle_end:
        current = razorpay.api("GET", f"subscriptions/{subscription.id}")
        if current.get("status") in TERMINAL_STATUSES:
            return sync_subscription(db, subscription, current)
        at_cycle_end = bool(current.get("paid_count")) and current.get("status") not in {"created", "authenticated"}
        entity = razorpay.api("POST", f"subscriptions/{subscription.id}/cancel", {"cancel_at_cycle_end": int(at_cycle_end)})
        subscription.cancel_at_cycle_end = at_cycle_end
        db.flush()
        return sync_subscription(db, subscription, entity)
    return plan_data(db, user)


@router.post("/sync", response_model=PlanResponse)
def reconcile(db: DbSession, current_user: CurrentUser):
    user = lock_user(db, current_user.id)
    subscription = latest_subscription(db, user.id)
    if not subscription:
        return plan_data(db, user)
    entity = razorpay.api("GET", f"subscriptions/{subscription.id}")
    payment = None
    if int(entity.get("paid_count") or 0) > subscription.paid_count:
        invoices = []
        for skip in (0, 100):
            page = razorpay.api("GET", f"invoices?subscription_id={subscription.id}&count=100&skip={skip}")["items"]
            invoices.extend(item for item in page if item.get("status") == "paid" and item.get("payment_id"))
            if len(page) < 100:
                break
        if invoices:
            invoice = max(invoices, key=lambda item: item.get("paid_at") or item.get("created_at") or 0)
            payment = razorpay.api("GET", f"payments/{invoice['payment_id']}")
    return sync_subscription(db, subscription, entity, payment)
