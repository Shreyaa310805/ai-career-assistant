"""Central entitlement and allowance rules; no payment-provider or AI calls."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.config import get_settings
from app.models.user import Plan, User
from app.models.subscription import InterviewUsage
from app.models.interview import Interview


def lock_user(db, user_id):
    return db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))


def started_interview(db, user_id, request_id):
    if request_id is None:
        return None
    return db.scalar(select(Interview).join(InterviewUsage).where(
        InterviewUsage.user_id == user_id, InterviewUsage.request_id == request_id))


def expire_access(db, user):
    if user.pro_until and user.pro_until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) and user.plan == Plan.PREMIUM:
        user = lock_user(db, user.id)
        if user.pro_until and user.pro_until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            user.plan = Plan.FREE
            user.interview_credits = 0
            db.commit()


def consume_interview(db, user, is_trial):
    condition = User.trial_used.is_(False) if is_trial else User.interview_credits > 0
    values = {"trial_used": True} if is_trial else {"interview_credits": User.interview_credits - 1}
    changed = db.execute(update(User).where(User.id == user.id, condition).values(**values))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(403, "Your lifetime trial is used. Upgrade to Pro." if is_trial else "No interview credits remain this billing period")


def check_question_access(interview, user, question_number):
    if not interview.is_trial and user.plan != Plan.PREMIUM:
        raise HTTPException(403, "An active Pro plan is required")
    if interview.is_trial and question_number > get_settings().free_trial_question_limit:
        raise HTTPException(403, "Your free interview trial is complete. Upgrade to Pro to start a new interview.")
