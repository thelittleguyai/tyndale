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
    anthropic_api_key: str | None = None  # Phase 2D — Lead Planner + subagents
    azure_doc_intelligence_endpoint: str | None = None  # Phase 2D — OCR
    azure_doc_intelligence_key: str | None = None  # Phase 2D — OCR
    litellm_proxy_url: str | None = None  # Phase 4 — proxy in front of Anthropic
    litellm_master_key: str | None = None  # Phase 4 — proxy admin key
    azure_key_vault_url: str | None = None  # Phase 4 — audit-log encryption keys
    azure_storage_account_url: str | None = None  # Phase 2D — uploaded document blobs
    azure_storage_uploads_container: str = "uploads"

    # --- Claude model assignments (locked per discipline rule D3) -------------
    # Resolution order at call time:
    #   1. claude_model_<role>_override (env var)
    #   2. claude_default_model_<tier>
    #   3. hard-coded fallback inside the agent
    claude_default_model_sonnet: str = "claude-sonnet-4-6"
    claude_default_model_opus: str = "claude-opus-4-7"
    claude_default_model_haiku: str = "claude-haiku-4-5"
    claude_model_lead_planner_override: str | None = None
    claude_model_bill_detective_override: str | None = None
    claude_model_math_person_override: str | None = None

    # Where to write uploaded files when running fully local (no Azure Blob).
    local_uploads_dir: str = "/tmp/tyndale_uploads"

    # Phase 2J — how long after a scripted recommendation before the dashboard
    # prompts the user for an outcome report. Default 14 days (per L05); tests
    # set 0 so freshly-created cases are eligible without time-travel.
    outcome_followup_days: int = 14

    # --- Knowledge layer (Qdrant + Voyage AI) ---
    # qdrant_url: an http(s):// URL connects to a server (Docker/Azure); any other
    # value (a filesystem path or ":memory:") uses qdrant-client's embedded local
    # mode — handy for Docker-less local dev (see app/knowledge/client.py).
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    voyage_api_key: str | None = None  # when unset, embeddings/rerank use a dev stub

    # Embedding model per collection (defaults are locked; override only for benchmarks).
    embedding_model_billing_codes: str = "voyage-3-large"
    embedding_model_error_detection: str = "voyage-3-large"
    embedding_model_laws: str = "voyage-context-3"
    embedding_model_payer_policies: str = "voyage-3-large"

    # --- Feature flags (off by default; stubs run when off) ---
    use_real_claude: bool = False
    use_real_ocr: bool = False
    use_real_presidio: bool = False  # security spine flips to true in Phase 4

    # Tighter knob: when use_real_claude is true but ANTHROPIC_API_KEY is unset
    # (e.g. running locally without creds), the agents fall back to fixtures
    # rather than raising. Set false in production.
    allow_fixture_fallback: bool = True

    def claude_model_for(self, role: str) -> str:
        """Resolve the Claude model for a given role.

        Roles: 'lead_planner' | 'bill_detective' | 'math_person'.
        Falls back to claude_default_model_sonnet for the V1-Lite trio per D3.
        """
        override = getattr(self, f"claude_model_{role}_override", None)
        if override:
            return override
        return self.claude_default_model_sonnet

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
