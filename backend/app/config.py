"""
Central configuration for Module 1 (Resume & ATS).

All settings have safe defaults so the module boots and runs with zero
external dependencies (SQLite database, local-disk mock file storage,
heuristic resume/JD parser instead of Gemini). This satisfies the
"independent module, zero blocking dependencies" requirement: Person 1's
service works stand-alone before Person 4's Postgres instance or a real
Gemini key ever exist.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "resume-ats-module"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./resume_ats.db"

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- Storage ---
    storage_backend: str = "local"  # local | supabase | cloudinary
    storage_local_dir: str = "./storage"
    storage_public_base_url: str = "https://storage.example.com/resumes"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "resumes"
    cloudinary_url: str = ""

    # --- Uploads ---
    max_upload_mb: int = 10

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
