"""
Global config facade: delegates to app.core.settings for backward compatibility.
Prefer importing get_settings() or Settings from app.core in new code.
"""
from pathlib import Path

from app.core.settings import get_settings

_s = get_settings()

# Paths
BASE_DIR: Path = _s.base_dir
DATABASE_DIR: Path = _s.database_dir
LEARNING_DATA_DIR: Path = _s.learning_data_dir
CHATS_DATA_DIR: Path = _s.chats_data_dir
VECTOR_STORE_DIR: Path = _s.vector_store_dir

# Tavily
TAVILY_API_KEY: str = _s.tavily_api_key

# OpenWeatherMap (weather / temperature)
OPENWEATHERMAP_API_KEY: str = _s.openweathermap_api_key
OPENWEATHERMAP_DEFAULT_CITY: str = _s.openweathermap_default_city

# Groq
GROQ_MODEL: str = _s.groq_model
USER_NAME: str = _s.user_name
ASSISTANT_NAME: str = _s.assistant_name
GROQ_API_KEYS: list = _s.groq_api_keys

# Ops
RATE_LIMIT_CHAT: str = _s.rate_limit_chat
LOG_FILE: str = _s.log_file

# MySQL
MYSQL_HOST: str = _s.mysql_host
MYSQL_PORT: int = _s.mysql_port
MYSQL_USER: str = _s.mysql_user
MYSQL_PASSWORD: str = _s.mysql_password
MYSQL_DATABASE: str = _s.mysql_database

# JWT
JWT_SECRET: str = _s.jwt_secret
JWT_ALGORITHM: str = _s.jwt_algorithm
JWT_EXPIRE_MINUTES: int = _s.jwt_expire_minutes

# Admin dashboard (comma-separated emails)
ADMIN_EMAILS: list = _s.admin_emails

# Murf TTS
MURF_API_KEY: str = _s.murf_api_key
MURF_REGION: str = _s.murf_region

# Reminders
REMINDER_WEBHOOK_URL: str = _s.reminder_webhook_url
REMINDER_CHECK_INTERVAL_SECONDS: int = _s.reminder_check_interval_seconds
INTERNAL_SECRET: str = _s.internal_secret

# Daily brief
BRIEF_HOUR: int = _s.brief_hour
