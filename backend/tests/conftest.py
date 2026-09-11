import os
import tempfile

# Must be configured before any application module constructs its SQLAlchemy engine.
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-long-enough-for-development-only"
for key in ("GEMINI_API_KEY", "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_PLAN_ID",
            "RAZORPAY_MONTHLY_PLAN_ID", "RAZORPAY_YEARLY_PLAN_ID", "RAZORPAY_WEBHOOK_SECRET"):
    os.environ[key] = ""  # Unit tests must never use developer credentials.

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)
