import os
import tempfile

# Must be configured before any application module constructs its SQLAlchemy engine.
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["JWT_SECRET_KEY"] = "test-secret-that-is-long-enough-for-development-only"
