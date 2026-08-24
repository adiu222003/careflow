"""
CareFlow — Healthcare Appointment & Follow-up Manager
Configuration via environment variables using Pydantic Settings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────────────
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str

    # ── Auth ───────────────────────────────────────────────────────────────
    jwt_secret: str
    jwt_expire_minutes: int = 60

    # ── OAuth token encryption ─────────────────────────────────────────────
    token_encryption_key: str = ""  # empty → calendar disabled automatically

    # ── AI / Gemini ────────────────────────────────────────────────────────
    enable_llm: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.0-flash"

    # ── Email / Resend ─────────────────────────────────────────────────────
    enable_email: bool = False
    resend_api_key: str = ""
    email_from: str = "noreply@careflow.demo"

    # ── Google Calendar ────────────────────────────────────────────────────
    enable_google_calendar: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    google_calendar_scope: str = "https://www.googleapis.com/auth/calendar.events"

    # ── Internal scheduler ────────────────────────────────────────────────
    internal_job_secret: str

    # ── CORS / URLs ───────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL must be set")
        return v

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
