"""Test-only account setup helpers; production access still requires verified billing."""
from uuid import UUID

from app.db.session import SessionLocal
from app.models.user import Plan, User


def grant_premium(user_id: str | UUID, credits: int = 10) -> None:
    with SessionLocal() as db:
        user = db.get(User, UUID(str(user_id)))
        assert user is not None
        user.plan = Plan.PREMIUM
        user.interview_credits = credits
        user.pro_until = None  # Legacy entitlement fixture, not a paid provider subscription.
        db.commit()
