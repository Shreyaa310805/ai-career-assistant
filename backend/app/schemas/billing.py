from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus
from app.models.user import Plan

BillingInterval = Literal["monthly", "yearly"]
PREMIUM_PRICE_CENTS = 1900  # Legacy response field; checkout amounts come from Razorpay.
PREMIUM_CURRENCY = "USD"  # Legacy response field; checkout currency comes from Razorpay.


class CheckoutRequest(BaseModel):
    plan: Plan = Plan.PREMIUM
    interval: BillingInterval = "monthly"


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    plan: Plan
    amount_cents: int
    currency: str
    provider: str
    status: PaymentStatus
    created_at: datetime


class CheckoutResponse(BaseModel):
    already_premium: bool
    key_id: str | None = None
    subscription_id: str | None = None
    amount: int | None = None
    currency: str | None = None


class PlanResponse(BaseModel):
    plan: Plan
    premium_since: datetime | None
    price_cents: int = PREMIUM_PRICE_CENTS
    currency: str = PREMIUM_CURRENCY
    provider: Literal["razorpay"] = "razorpay"
    payments: list[PaymentResponse]
    credits: int
    credit_limit: int
    trial_available: bool
    trial_question_limit: int
    interval: BillingInterval
    pro_until: datetime | None
    subscription_id: str | None
    subscription_status: str | None
    cancel_at_cycle_end: bool
    webhook_configured: bool
    test_mode: bool = True
    configured: bool
