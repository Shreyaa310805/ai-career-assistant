"""Subscription expiry and shared entitlement primitives."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.user import Plan, User


def lock_user(db, user_id):
    return db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def expire_access(db, user: User) -> User:
    until = user.pro_until
    if until is None or user.plan != Plan.PREMIUM:
        return user
    if until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        locked = lock_user(db, user.id)
        if locked and locked.pro_until and locked.pro_until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            locked.plan = Plan.FREE
            locked.interview_credits = 0
            db.commit()
        return locked or user
    return user
