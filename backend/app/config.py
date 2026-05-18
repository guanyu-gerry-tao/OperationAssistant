from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    # Keep environment variable names grouped under OA_ so local shell config is predictable.
    model_config = SettingsConfigDict(env_prefix="OA_", env_file=".env", extra="ignore")

    # M1 can run without external services, so dependency URLs stay optional.
    app_name: str = "operation-assistant-api"
    database_url: str | None = None
    redis_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings for request handlers."""

    # Cache settings so each request does not re-read the environment and .env file.
    return Settings()
