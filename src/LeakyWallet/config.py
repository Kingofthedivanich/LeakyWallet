from functools import lru_cache

from pydantic import RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    telegram_bot_token: str = ""
    telegram_use_webhook: bool = False
    telegram_webhook_url: str | None = None
    telegram_webhook_secret: str | None = None

    database_url: str
    redis_url: RedisDsn

    fernet_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
