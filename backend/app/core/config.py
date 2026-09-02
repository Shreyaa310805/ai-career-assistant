from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ai_career:change-me-in-production@localhost:5432/ai_career"
    jwt_secret_key: str = "development-only-change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    frontend_origin: str = "http://localhost:3000"
    resume_database_url: str = "sqlite+aiosqlite:///./resume_ats.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    storage_backend: str = "local"
    storage_local_dir: str = "./storage"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "resumes"
    cloudinary_url: str = ""
    max_upload_mb: int = 10

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
