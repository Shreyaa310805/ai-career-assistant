"""
File storage abstraction (ISSUE-10). Ships with a local-disk mock backend
so the module has zero external dependency on Supabase/Cloudinary during
standalone development; swapping STORAGE_BACKEND in .env activates the real
integrations without touching calling code.
"""
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings
from app.exceptions import StorageError

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        """Persist the file and return a publicly-addressable file_url."""


class LocalMockStorage(StorageBackend):
    """Writes to STORAGE_LOCAL_DIR and fabricates a URL shaped like the
    real Supabase/Cloudinary public URL the frontend expects
    (see the upload endpoint contract's `file_url` example)."""

    def __init__(self) -> None:
        self.base_dir = Path(settings.storage_local_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        filename = f"{resume_id}{extension}"
        path = self.base_dir / filename
        try:
            path.write_bytes(file_bytes)
        except OSError as exc:
            raise StorageError(f"Failed to persist uploaded file: {exc}") from exc
        base = settings.storage_public_base_url.rstrip("/")
        return f"{base}/{filename}"


class SupabaseStorage(StorageBackend):
    """Placeholder for real Supabase Storage integration. Wire up with the
    `supabase` client + settings.supabase_url / supabase_service_key /
    supabase_bucket once credentials exist; interface stays identical so no
    caller changes are needed."""

    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        raise StorageError(
            "Supabase storage backend selected but not yet configured. "
            "Set SUPABASE_URL/SUPABASE_SERVICE_KEY or use STORAGE_BACKEND=local."
        )


class CloudinaryStorage(StorageBackend):
    """Placeholder for real Cloudinary integration — same rationale as
    SupabaseStorage above."""

    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        raise StorageError(
            "Cloudinary storage backend selected but not yet configured. "
            "Set CLOUDINARY_URL or use STORAGE_BACKEND=local."
        )


def get_storage_backend() -> StorageBackend:
    backend = settings.storage_backend.lower()
    if backend == "supabase":
        return SupabaseStorage()
    if backend == "cloudinary":
        return CloudinaryStorage()
    return LocalMockStorage()


def new_resume_id() -> str:
    return str(uuid.uuid4())
