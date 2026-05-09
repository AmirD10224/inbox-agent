"""Application configuration loaded from environment variables.

All env vars are validated at process start; misconfiguration fails fast rather
than surfacing as a 500 deep inside a request.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Anthropic ────────────────────────────────────────────────
    anthropic_api_key: SecretStr = Field(
        default=SecretStr("test-key"),
        description="Anthropic API key. The default 'test-key' is overwritten in tests via respx.",
    )
    anthropic_model_primary: str = "claude-sonnet-4-6"
    anthropic_model_judge: str = "claude-haiku-4-5-20251001"
    anthropic_max_retries: int = 3
    anthropic_timeout_s: float = 30.0

    # ── Voyage embeddings ────────────────────────────────────────
    voyage_api_key: SecretStr = Field(default=SecretStr("test-key"))
    voyage_embed_model: str = "voyage-3"

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://inbox:inbox@localhost:5432/inbox_agent"

    # ── Langfuse ─────────────────────────────────────────────────
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── App ──────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def langfuse_enabled(self) -> bool:
        return self.langfuse_public_key is not None and self.langfuse_secret_key is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
