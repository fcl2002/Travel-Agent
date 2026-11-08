"""Application configuration from environment variables or a local .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://travel_agent:travel_agent_dev@localhost:5433/travel_agent"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
