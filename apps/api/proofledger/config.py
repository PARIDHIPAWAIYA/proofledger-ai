from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROOFLEDGER_",
        extra="ignore",
    )

    env: str = "development"
    database_url: str = "sqlite:///./proofledger.db"
    cors_origins: str = "http://localhost:5173"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

