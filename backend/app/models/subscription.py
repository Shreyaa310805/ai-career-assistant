from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func, text
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from uuid import UUID


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("uq_subscription_open_user", "user_id", unique=True,
        postgresql_where=text("status NOT IN ('cancelled', 'completed', 'expired')"),
        sqlite_where=text("status NOT IN ('cancelled', 'completed', 'expired')")),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(80), nullable=False)
    interval: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    paid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credit_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_at_cycle_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SubscriptionCharge(Base):
    __tablename__ = "subscription_charges"
    payment_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String(80), ForeignKey("subscriptions.id"), nullable=False)


class InterviewUsage(Base):
    __tablename__ = "interview_usage"
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_interview_usage_request"),)
    interview_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("interviews.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    credits_charged: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
