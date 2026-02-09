"""
Application settings loaded from environment (.env).
Single source of truth with validation at import time.
"""
import os
from pathlib import Path
from typing import List

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Validated configuration from env and .env file."""

    model_config = SettingsConfigDict(
        env_file=_project_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent

    # Tavily
    tavily_api_key: str = ""

    # OpenWeatherMap (weather / temperature; use this instead of Tavily for temp queries)
    openweathermap_api_key: str = Field(default="", validation_alias="OPENWEATHERMAP_API_KEY")
    openweathermap_default_city: str = Field(default="Delhi", validation_alias="OPENWEATHERMAP_DEFAULT_CITY")

    # Groq (GROQ_API_KEYS = comma-separated, or GROQ_API_KEY = single key)
    groq_model: str = "llama-3.1-70b-versatile"
    user_name: str = "User"
    assistant_name: str = "Jarvis"
    groq_api_keys: List[str] = []
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")

    # Ops
    rate_limit_chat: str = "30/minute"
    log_file: str = "logs/jarvisai.log"

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "jarvisai"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Admin dashboard: comma-separated emails that can access /admin/* (stored as str to avoid JSON parse from env)
    admin_emails_str: str = Field(default="", validation_alias="ADMIN_EMAILS")

    # Default seeded admin (dashboard admins table). Set in .env only; no defaults to avoid leaking credentials.
    default_admin_email: str = Field(default="", validation_alias="DEFAULT_ADMIN_EMAIL")
    default_admin_password: str = Field(default="", validation_alias="DEFAULT_ADMIN_PASSWORD")

    @computed_field
    @property
    def DEFAULT_ADMIN_EMAIL(self) -> str:
        """Backward-compat alias for default_admin_email."""
        return self.default_admin_email

    # Murf TTS (daily brief voice). Get key: https://murf.ai/api
    murf_api_key: str = Field(default="", validation_alias="MURF_API_KEY")
    murf_region: str = Field(default="GLOBAL", validation_alias="MURF_REGION")

    # Reminders: optional webhook URL for due reminders (Discord/Telegram etc.)
    reminder_webhook_url: str = Field(default="", validation_alias="REMINDER_WEBHOOK_URL")
    reminder_check_interval_seconds: int = Field(default=60, validation_alias="REMINDER_CHECK_INTERVAL_SECONDS")
    internal_secret: str = Field(default="", validation_alias="INTERNAL_SECRET")

    # Daily brief: hour (0-23) to generate brief; timezone is server local
    brief_hour: int = Field(default=7, ge=0, le=23, validation_alias="BRIEF_HOUR")

    @computed_field
    @property
    def admin_emails(self) -> List[str]:
        emails = [x.strip() for x in self.admin_emails_str.split(",") if x.strip()]
        default_lower = self.DEFAULT_ADMIN_EMAIL.lower()
        if default_lower and default_lower not in [e.lower() for e in emails]:
            emails.append(self.DEFAULT_ADMIN_EMAIL)
        return emails

    @property
    def database_dir(self) -> Path:
        return self.base_dir / "database"

    @property
    def learning_data_dir(self) -> Path:
        return self.database_dir / "learning_data"

    @property
    def chats_data_dir(self) -> Path:
        return self.database_dir / "chats_data"

    @property
    def vector_store_dir(self) -> Path:
        return self.database_dir / "vector_store"

    @field_validator("groq_api_keys", mode="before")
    @classmethod
    def parse_comma_list(cls, v: object) -> List[str]:
        if isinstance(v, list):
            return [x.strip() for x in v if isinstance(x, str) and x.strip()]
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return []

    @model_validator(mode="after")
    def groq_fallback_single_key(self) -> "Settings":
        """If groq_api_keys is empty, use groq_api_key (GROQ_API_KEY from .env)."""
        if not self.groq_api_keys and self.groq_api_key:
            object.__setattr__(self, "groq_api_keys", [self.groq_api_key.strip()])
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return singleton settings instance. Validates and creates dirs on first access."""
    global _settings
    if _settings is None:
        _settings = Settings()
        # Ensure directories exist
        _settings.learning_data_dir.mkdir(parents=True, exist_ok=True)
        _settings.chats_data_dir.mkdir(parents=True, exist_ok=True)
        _settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    return _settings
