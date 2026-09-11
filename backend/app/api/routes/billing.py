"""Verified Razorpay TEST subscriptions and monthly interview credits."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.user import Plan, User
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionCharge
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PaymentResponse, PlanResponse
from app.services import razorpay
from app.services.entitlements import lock_user

router = APIRouter(prefix="/billing", tags=["billing"])


def latest_subscription(db, user_id):
    return db.scalar(select(Subscription).where(Subscription.user_id == user_id,
        Subscription.status.notin_(["cancelled", "completed", "expired"])))


def plan_data(db, user):
    sub = latest_subscription(db, user.id)
    settings = get_settings()
    interval = sub.interval if sub else "monthly"
    return {"plan": user.plan, "credits": user.interview_credits if user.plan == Plan.PREMIUM else 0,
        "credit_limit": (sub.credit_limit if sub and sub.credit_limit else settings.interview_allowance(interval)), "trial_available": not user.trial_used, "pro_until": user.pro_until,
        "trial_question_limit": settings.free_trial_question_limit, "interval": interval,
        "webhook_configured": bool(settings.razorpay_webhook_secret),
        "subscription_id": sub.id if sub else None, "subscription_status": sub.status if sub else None,
        "cancel_at_cycle_end": sub.cancel_at_cycle_end if sub else False,
        "provider": "razorpay", "test_mode": True, "configured": razorpay.configured()}


@router.get("/catalog")
def catalog(current_user: CurrentUser):
    settings = get_settings()
    plans = []
    for interval in ("monthly", "yearly"):
        plan_id = settings.provider_plan_id(interval)
        item = {"interval": interval, "available": bool(plan_id) and razorpay.configured(),
                "credits": settings.interview_allowance(interval), "amount": None, "currency": None}
        if item["available"]:
            entity = razorpay.api("GET", f"plans/{plan_id}")
            item["available"] = entity.get("period") == interval and entity.get("interval") == 1
            item.update(amount=entity["item"]["amount"], currency=entity["item"]["currency"])
        plans.append(item)
    return {"plans": plans, "trial_question_limit": settings.free_trial_question_limit}


@router.get("/plan", response_model=PlanResponse)
def get_plan(db: DbSession, current_user: CurrentUser):
    return plan_data(db, current_user)


@router.get("/payments", response_model=list[PaymentResponse])
def payment_history(db: DbSession, current_user: CurrentUser):
    return db.scalars(select(Payment).where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc()).limit(100)).all()


@router.post("/checkout", status_code=201, response_model=CheckoutResponse, response_model_exclude_none=True)
def checkout(payload: CheckoutRequest, db: DbSession, current_user: CurrentUser):
    if payload.plan != Plan.PREMIUM:
        raise HTTPException(422, "Only Pro can be purchased")
    user = lock_user(db, current_user.id)
    if user.plan == Plan.PREMIUM:
        return {"already_premium": True}
    settings = get_settings()
    plan_id = settings.provider_plan_id(payload.interval)
    if not plan_id:
        raise HTTPException(503, "This billing interval is not configured yet")
    plan = razorpay.api("GET", f"plans/{plan_id}")
    if plan.get("period") != payload.interval or plan.get("interval") != 1:
        raise HTTPException(503, "The Razorpay plan billing interval does not match configuration")
    sub = latest_subscription(db, user.id)
    if sub:
        current = razorpay.api("GET", f"subscriptions/{sub.id}")
        if current.get("status") in {"cancelled", "completed", "expired"}:
            sync_subscription(db, sub, current)
            user = lock_user(db, user.id)
            sub = latest_subscription(db, user.id)
    if sub and sub.plan_id != plan_id:
        raise HTTPException(409, "An unfinished subscription exists for another billing interval. Cancel it first.")
    if sub is None:
        entity = razorpay.api("POST", "subscriptions", {"plan_id": plan_id,
            "total_count": 120 if payload.interval == "monthly" else 10, "quantity": 1, "customer_notify": 1, "notes": {"user_id": str(user.id)}})
        sub = Subscription(id=entity["id"], user_id=user.id, plan_id=plan_id, interval=payload.interval)
        db.add(sub)
        db.commit()
    return {"already_premium": False, "key_id": settings.razorpay_key_id,
        "subscription_id": sub.id, "amount": plan["item"]["amount"], "currency": plan["item"]["currency"]}


def sync_subscription(db, sub, entity, payment=None):
    """Fresh provider state and paid_count prevent replay from refilling credits."""
    user = lock_user(db, sub.user_id)
    db.refresh(sub)
    if entity.get("id") != sub.id or entity.get("plan_id") != sub.plan_id:
        raise HTTPException(400, "Subscription does not match the purchased plan")
    state = entity["status"]
    paid_count = int(entity.get("paid_count") or 0)
    if payment is not None:
        if payment.get("status") != "captured" or not payment.get("invoice_id"):
            raise HTTPException(409, "Payment is not captured yet; wait for confirmation")
        invoice = razorpay.api("GET", f"invoices/{payment['invoice_id']}")
        if invoice.get("subscription_id") != sub.id or invoice.get("payment_id") != payment["id"] or invoice.get("status") != "paid":
            raise HTTPException(400, "Payment does not belong to this subscription")
        if not db.get(SubscriptionCharge, payment["id"]):
            db.add(SubscriptionCharge(payment_id=payment["id"], subscription_id=sub.id))
            db.add(Payment(user_id=user.id, plan=Plan.PREMIUM, amount_cents=payment["amount"],
                currency=payment["currency"], provider="razorpay", status=PaymentStatus.SUCCEEDED))
        if paid_count > sub.paid_count and state in {"active", "pending", "halted"}:
            end = entity.get("current_end")
            if not end:
                raise HTTPException(409, "Waiting for the subscription billing period")
            user.pro_until = datetime.fromtimestamp(end, timezone.utc)
            if user.pro_until > datetime.now(timezone.utc):
                user.plan = Plan.PREMIUM
                user.interview_credits = get_settings().interview_allowance(sub.interval)
                sub.credit_limit = user.interview_credits
            sub.paid_count = paid_count
    sub.status = state
    if state in {"cancelled", "completed", "expired"}:
        sub.cancel_at_cycle_end = False
        newer = db.scalar(select(Subscription).where(Subscription.user_id == user.id,
            Subscription.id != sub.id, Subscription.status.notin_(["cancelled", "completed", "expired"])))
        if newer is None:
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
    lock_user(db, current_user.id)
    sub = db.get(Subscription, payload.razorpay_subscription_id)
    if not sub or sub.user_id != current_user.id:
        raise HTTPException(404, "Subscription not found")
    razorpay.verify_signature(f"{payload.razorpay_payment_id}|{sub.id}".encode(),
        payload.razorpay_signature, get_settings().razorpay_key_secret)
    entity = razorpay.api("GET", f"subscriptions/{sub.id}")
    payment = razorpay.api("GET", f"payments/{payload.razorpay_payment_id}")
    return sync_subscription(db, sub, entity, payment)


@router.post("/webhook")
async def webhook(request: Request, db: DbSession):
    if not get_settings().razorpay_webhook_secret:
        raise HTTPException(503, "Webhook verification is not configured")
    raw = await request.body()
    razorpay.verify_signature(raw, request.headers.get("x-razorpay-signature", ""), get_settings().razorpay_webhook_secret)
    try:
        event = json.loads(raw)
        event_type = event["event"]
        if event_type not in {"subscription.charged", "subscription.cancelled", "subscription.completed",
                              "subscription.halted", "subscription.pending", "subscription.activated", "subscription.authenticated"}:
            return {"received": True}
        sub_id = event["payload"]["subscription"]["entity"]["id"]
        payment = event["payload"]["payment"]["entity"] if event_type == "subscription.charged" else None
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Malformed webhook")
    sub = db.get(Subscription, sub_id)
    if sub:
        lock_user(db, sub.user_id)
        entity = razorpay.api("GET", f"subscriptions/{sub.id}")
        sync_subscription(db, sub, entity, payment)
    return {"received": True}


@router.post("/cancel", response_model=PlanResponse)
def cancel(db: DbSession, current_user: CurrentUser):
    user = lock_user(db, current_user.id)
    sub = latest_subscription(db, user.id)
    if sub and not sub.cancel_at_cycle_end:
        current = razorpay.api("GET", f"subscriptions/{sub.id}")
        if current.get("status") in {"cancelled", "completed", "expired"}:
            return sync_subscription(db, sub, current)
        at_end = bool(current.get("paid_count")) and current.get("status") not in {"created", "authenticated"}
        entity = razorpay.api("POST", f"subscriptions/{sub.id}/cancel", {"cancel_at_cycle_end": int(at_end)})
        sub.cancel_at_cycle_end = at_end
        db.flush()
        return sync_subscription(db, sub, entity)
    return plan_data(db, user)


@router.post("/sync", response_model=PlanResponse)
def reconcile(db: DbSession, current_user: CurrentUser):
    """Authenticated recovery when a callback is lost or webhooks are not configured locally."""
    user = lock_user(db, current_user.id)
    sub = latest_subscription(db, user.id)
    if not sub:
        return plan_data(db, user)
    entity = razorpay.api("GET", f"subscriptions/{sub.id}")
    payment = None
    if int(entity.get("paid_count") or 0) > sub.paid_count:
        invoices = []
        for skip in (0, 100):
            page = razorpay.api("GET", f"invoices?subscription_id={sub.id}&count=100&skip={skip}")["items"]
            invoices.extend(i for i in page if i.get("status") == "paid" and i.get("payment_id"))
            if len(page) < 100:
                break
        if invoices:
            invoice = max(invoices, key=lambda i: i.get("paid_at") or i.get("created_at") or 0)
            payment = razorpay.api("GET", f"payments/{invoice['payment_id']}")
    return sync_subscription(db, sub, entity, payment)
