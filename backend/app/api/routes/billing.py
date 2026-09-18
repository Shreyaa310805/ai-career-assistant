"""Plan upgrades.

The payment provider is simulated: `POST /billing/checkout` records a mock
transaction and flips the account to PREMIUM. No card details are accepted,
transmitted or stored anywhere in this flow.

The plan value is decided entirely server-side. A client can ask to buy
PREMIUM; it can never assert that it already has it -- every premium feature
re-reads `users.plan` through `require_premium`.
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.payment import Payment, PaymentStatus
from app.models.user import Plan
from app.schemas.billing import (
    PREMIUM_CURRENCY,
    PREMIUM_PRICE_CENTS,
    CheckoutRequest,
    CheckoutResponse,
    PaymentResponse,
    PlanResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])


def _payments_for(db: DbSession, user_id) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
        ).all()
    )


@router.get("/plan", response_model=PlanResponse)
def get_plan(db: DbSession, current_user: CurrentUser):
    payments = _payments_for(db, current_user.id)
    upgrade = next(
        (p for p in reversed(payments) if p.plan == Plan.PREMIUM and p.status == PaymentStatus.SUCCEEDED),
        None,
    )
    return PlanResponse(
        plan=current_user.plan,
        premium_since=upgrade.created_at if upgrade else None,
        payments=[PaymentResponse.model_validate(p) for p in payments],
    )


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, db: DbSession, current_user: CurrentUser):
    if payload.plan != Plan.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only the PREMIUM plan can be purchased",
        )
    # Re-running checkout must not double-charge or duplicate the upgrade.
    if current_user.plan == Plan.PREMIUM:
        return CheckoutResponse(user=current_user, payment=None, already_premium=True)

    payment = Payment(
        user_id=current_user.id,
        plan=Plan.PREMIUM,
        amount_cents=PREMIUM_PRICE_CENTS,
        currency=PREMIUM_CURRENCY,
        provider="mock",
        status=PaymentStatus.SUCCEEDED,
    )
    current_user.plan = Plan.PREMIUM
    db.add(payment)
    db.commit()
    db.refresh(payment)
    db.refresh(current_user)

    return CheckoutResponse(
        user=current_user,
        payment=PaymentResponse.model_validate(payment),
        already_premium=False,
    )
