"""Application configuration with fail-fast environment validation.

DATABASE_URL is required and has no default — a missing value raises at startup
(import of app.db.base calls get_settings()), which is the intended fail-fast.
"""

from __future__ import annotations

from functools import lru_cache

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

log = structlog.get_logger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Server (defaults provided) ---
    node_env: str = Field(default="development", description="development | staging | production")
    port: int = Field(default=4000)
    log_level: str = Field(default="info")
    cors_allowed_origins: str = Field(default="", description="comma-separated origin allow-list")

    # --- Database (REQUIRED — fail-fast if absent) ---
    database_url: str = Field(description="asyncpg DSN, e.g. postgresql+asyncpg://user:pw@host/db")

    # --- Optional integrations (warned if missing in production) ---
    anthropic_api_key: str | None = None  # Phase 2
    azure_doc_intelligence_endpoint: str | None = None  # Phase 2
    azure_doc_intelligence_key: str | None = None  # Phase 2
    litellm_proxy_url: str | None = None  # Phase 4
    azure_key_vault_url: str | None = None  # Phase 4 — audit-log encryption keys

    # --- Feature flags (off by default; stubs run when off) ---
    use_real_claude: bool = False
    use_real_ocr: bool = False
    use_real_presidio: bool = False  # security spine flips to true in Phase 4

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"

    def warn_missing_in_prod(self) -> None:
        """Log a warning for each prod-relevant optional var that is unset."""
        if not self.is_production:
            return
        for var in (
            "anthropic_api_key",
            "azure_doc_intelligence_endpoint",
            "litellm_proxy_url",
            "azure_key_vault_url",
        ):
            if not getattr(self, var):
                log.warning("config.missing_optional_in_prod", var=var.upper())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
