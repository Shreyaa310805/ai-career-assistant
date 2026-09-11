from uuid import UUID
from app.db.session import SessionLocal
from app.models.user import Plan, User


def grant_premium(user_id):
    """Fixture entitlement only. Payment verification has its own integration tests."""
    with SessionLocal() as db:
        user = db.get(User, UUID(str(user_id)))
        user.plan = Plan.PREMIUM
        user.interview_credits = 10
        db.commit()
