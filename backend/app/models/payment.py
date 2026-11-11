import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import Plan


class PaymentStatus(str, enum.Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class Payment(Base):
    """An audited payment record; provider payment identifiers live in SubscriptionCharge."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    plan: Mapped[Plan] = mapped_column(Enum(Plan, name="plan_type"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock", server_default="mock")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="payment_status"), nullable=False, default=PaymentStatus.SUCCEEDED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", backref="payments")
