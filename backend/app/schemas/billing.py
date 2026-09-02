from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus
from app.models.user import Plan
from app.schemas.auth import UserResponse

# Simulated pricing. A real integration would read this from the processor.
PREMIUM_PRICE_CENTS = 1900
PREMIUM_CURRENCY = "USD"


class CheckoutRequest(BaseModel):
    """The plan the user is buying.

    Only the target plan is accepted -- never a price, and never card data.
    The server owns the amount and the resulting plan state.
    """

    plan: Plan = Plan.PREMIUM


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
    user: UserResponse
    payment: PaymentResponse | None
    already_premium: bool


class PlanResponse(BaseModel):
    plan: Plan
    premium_since: datetime | None
    price_cents: int = PREMIUM_PRICE_CENTS
    currency: str = PREMIUM_CURRENCY
    provider: str = "mock"
    payments: list[PaymentResponse]
