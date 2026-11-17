"""Application configuration from environment variables or a local .env file."""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = (
        "postgresql+psycopg://travel_agent:travel_agent_dev@localhost:5433/travel_agent"
    )
    jwt_secret_key: SecretStr | None = Field(default=None, min_length=32)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    refresh_cookie_secure: bool = True
    frontend_origin: str | None = None
    jwt_issuer: str = "travel-agent"
    jwt_audience: str = "travel-agent-api"

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def empty_secret(cls, value):
        return None if value == "" else value

    @field_validator("frontend_origin", mode="before")
    @classmethod
    def clean_frontend_origin(cls, value):
        if not value:
            return None
        origin = urlsplit(value)
        if (origin.scheme not in {"http", "https"} or not origin.hostname
                or origin.username or origin.password or "*" in origin.netloc
                or origin.path not in {"", "/"} or origin.query or origin.fragment):
            raise ValueError("FRONTEND_ORIGIN must be one exact HTTP(S) origin without a path or wildcard")
        _ = origin.port  # Validate the optional port.
        return f"{origin.scheme}://{origin.netloc.lower()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
