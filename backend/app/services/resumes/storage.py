"""
File storage abstraction (ISSUE-10). Ships with a local-disk mock backend
so the module has zero external dependency on Supabase/Cloudinary during
standalone development; swapping STORAGE_BACKEND in .env activates the real
integrations without touching calling code.
"""
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings
from app.services.resumes.exceptions import StorageError

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        """Persist the file and return a server-side storage identifier."""


class LocalMockStorage(StorageBackend):
    """Writes private uploaded files to STORAGE_LOCAL_DIR."""

    def __init__(self) -> None:
        self.base_dir = Path(settings.storage_local_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir.chmod(0o700)

    async def save(self, file_bytes: bytes, extension: str, resume_id: str) -> str:
        filename = f"{resume_id}{extension}"
        path = self.base_dir / filename
        try:
            path.write_bytes(file_bytes)
            path.chmod(0o600)
        except OSError as exc:
            raise StorageError(f"Failed to persist uploaded file: {exc}") from exc
        # The file is never exposed through a public URL.
        return f"local://resumes/{filename}"


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
