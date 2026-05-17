from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="OA_", env_file=".env", extra="ignore")

    app_name: str = "operation-assistant-api"
    database_url: str | None = None
    redis_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings for request handlers."""

    return Settings()
