import os
import tempfile

# Must be configured before any application module constructs its SQLAlchemy engine.
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-long-enough-for-development-only"

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)
