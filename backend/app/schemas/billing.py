from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict
from app.models.payment import PaymentStatus
from app.models.user import Plan

BillingInterval = Literal["monthly", "yearly"]


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    plan: Plan
    amount_cents: int
    currency: str
    provider: str
    status: PaymentStatus
    created_at: datetime


class CheckoutRequest(BaseModel):
    plan: Plan = Plan.PREMIUM
    interval: BillingInterval = "monthly"


class CheckoutResponse(BaseModel):
    already_premium: bool
    key_id: str | None = None
    subscription_id: str | None = None
    amount: int | None = None
    currency: str | None = None


class PlanResponse(BaseModel):
    plan: Plan
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
    provider: Literal["razorpay"]
    test_mode: bool
    configured: bool
