from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[3] / ".env", Path(__file__).resolve().parents[2] / ".env"),
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ai_career:change-me-in-production@localhost:5432/ai_career"
    jwt_secret_key: str = "development-only-change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    frontend_origin: str = "http://localhost:3000"
    resume_database_url: str = "sqlite+aiosqlite:///./resume_ats.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    storage_backend: str = "local"
    storage_local_dir: str = "./storage"
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "resumes"
    cloudinary_url: str = ""
    max_upload_mb: int = 10
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_plan_id: str = ""
    razorpay_monthly_plan_id: str = ""
    razorpay_yearly_plan_id: str = ""
    pro_monthly_interview_credits: int = Field(default=10, ge=1)
    pro_yearly_interview_credits: int = Field(default=120, ge=1)
    free_trial_question_limit: int = Field(default=3, ge=1)

    def provider_plan_id(self, interval: str) -> str:
        return (self.razorpay_monthly_plan_id or self.razorpay_plan_id) if interval == "monthly" else self.razorpay_yearly_plan_id

    def interview_allowance(self, interval: str) -> int:
        return self.pro_monthly_interview_credits if interval == "monthly" else self.pro_yearly_interview_credits

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
