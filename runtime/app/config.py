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
    # Phase CO-3A — bulk data staging (CMS/PFS/Hospital MRF/TiC downloads).
    # When the connection string is unset (dev/CI/tests), BlobStorage falls back
    # to the local filesystem at bulk_local_dir.
    azure_storage_connection_string: str | None = None
    azure_storage_bulk_container: str = "bulk-data"
    bulk_local_dir: str = "/tmp/tyndale_bulk"

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

    # --- Auth (Phase 2K) ------------------------------------------------------
    # USE_REAL_AUTH=false keeps the dev-mode current_user stub (the seeded admin
    # user) so local dev works without Google creds. MUST be true in production.
    use_real_auth: bool = False
    auth_secret: str | None = None  # HS256 signing key for session + magic-link JWTs
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "https://dev.tyndaleapp.net/v1/auth/callback"
    sendgrid_api_key: str | None = None  # Email API Pro tier (BAA) per DL-18
    sendgrid_from_email: str = "no-reply@tyndaleapp.net"
    magic_link_ttl_minutes: int = 15
    magic_link_base_url: str = "https://dev.tyndaleapp.net"  # where verify links point
    session_cookie_name: str = "tyndale_session"
    session_ttl_hours: int = 24 * 7  # 7 days
    cookie_domain: str = "tyndaleapp.net"  # blank ("") for localhost dev
    cookie_secure: bool = True  # false only for http://localhost
    auth_success_redirect: str = "https://dev.tyndaleapp.net/signed-in"
    # Rate limits for magic-link requests (sliding window, in-memory for V1-Lite).
    magic_link_rate_per_email_hour: int = 5
    magic_link_rate_per_ip_hour: int = 20

    # --- Hardening (Phase 2K.2 / DL-46) --------------------------------------
    # Fills the gap from DL-42 (runtime went public at api.tyndaleapp.net). All
    # rate limits are in-memory per-replica (Phase 4 → Redis). Disabled in the
    # test suite via RATE_LIMIT_ENABLED=false.
    rate_limit_enabled: bool = True
    rate_limit_per_ip_per_minute: int = 100
    rate_limit_per_ip_per_hour: int = 1000
    rate_limit_per_user_per_minute: int = 200
    rate_limit_per_user_per_hour: int = 2000
    # Per-route hourly caps for expensive ops (per authenticated user, else IP).
    rate_limit_upload_per_hour: int = 20
    rate_limit_extract_per_hour: int = 20
    rate_limit_finalize_per_hour: int = 20
    rate_limit_confirmations_per_hour: int = 50
    # Trust the first IP from this many X-Forwarded-For hops (Container Apps' LB
    # prepends 1). Never trust an unbounded XFF chain.
    trust_forwarded_for_hops: int = 1

    security_headers_enabled: bool = True

    # Request body size limits (bytes).
    max_request_body_bytes: int = 25 * 1024 * 1024  # 25 MB — multipart ceiling
    max_json_body_bytes: int = 1 * 1024 * 1024  # 1 MB — JSON bodies
    max_upload_file_bytes: int = 20 * 1024 * 1024  # 20 MB — per uploaded file

    # Admin IP allowlist (comma-separated CIDR; empty = no restriction). Applies
    # to /v1/admin/* — preventive; no admin routes exist yet.
    admin_allowed_ips: str = ""

    # __Secure- cookie prefix (OWASP / RFC 6265bis). Applied to the session
    # cookie name ONLY when cookie_secure is true — a __Secure- cookie sent over
    # plain http is rejected by browsers, which would break local dev/tests.
    session_cookie_secure_prefix: bool = True

    def has_real_auth_secret(self) -> bool:
        key = (self.auth_secret or "").strip()
        return bool(key) and not key.startswith("<")

    # --- Cookie naming (Phase 2K.2) ------------------------------------------
    @property
    def session_cookie_write_name(self) -> str:
        """Name used to SET the session cookie. Gets the __Secure- prefix only
        over HTTPS (cookie_secure); plain-http dev keeps the bare name."""
        base = self.session_cookie_name
        if (
            self.cookie_secure
            and self.session_cookie_secure_prefix
            and not base.startswith("__Secure-")
        ):
            return f"__Secure-{base}"
        return base

    @property
    def session_cookie_read_names(self) -> list[str]:
        """Names accepted when READING the session cookie: the current write
        name + the legacy bare name (30-day grace so existing sessions survive
        the __Secure- cutover without logging anyone out — DL-46)."""
        out: list[str] = []
        for n in (self.session_cookie_write_name, self.session_cookie_name):
            if n not in out:
                out.append(n)
        return out

    @property
    def admin_allowed_cidrs(self) -> list[str]:
        return [c.strip() for c in self.admin_allowed_ips.split(",") if c.strip()]

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
    # rather than raising. Defaults False (CO-15) — a prod deploy must NEVER
    # silently serve the MRI fixture as a real audit; see assert_production_safety().
    allow_fixture_fallback: bool = False

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

    def assert_production_safety(self) -> None:
        """Fail-fast guard (CO-15): a production deploy must never silently serve
        fixtures. In production, ``allow_fixture_fallback`` MUST be False and
        ``use_real_claude`` MUST be True — otherwise a missing/invalid Anthropic
        key would return the MRI fixture ($560) as if it were a real audit. Called
        from main.py's lifespan so an unsafe prod config fails to boot."""
        if not self.is_production:
            return
        problems: list[str] = []
        if self.allow_fixture_fallback:
            problems.append("ALLOW_FIXTURE_FALLBACK must be false in production")
        if not self.use_real_claude:
            problems.append("USE_REAL_CLAUDE must be true in production")
        if problems:
            raise RuntimeError("Unsafe production config — " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
