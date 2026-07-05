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
    # AES-GCM key for audit-log payload encryption (Key Vault-backed env; base64 of
    # 32 raw bytes = AES-256). When set, PostToolUse encrypts payloads before store
    # and readers decrypt on read; when None (dev), payloads stay clear-text JSON and
    # a startup warning is logged. See app/security/audit_crypto.py.
    audit_log_enc_key: str | None = None
    audit_log_key_version: int = 1  # stamped on rows written under audit_log_enc_key
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

    # --- Azure AI Foundry (CO-18 / DL-79) -------------------------------------
    # Route Claude through Microsoft Foundry (the Anthropic Messages API at
    # {foundry_endpoint}/anthropic) using the runtime's MANAGED IDENTITY — no API
    # key — so Azure's BAA covers Claude. ``use_foundry`` flips the client factory;
    # ``foundry_endpoint`` is the account base URL (Terraform local.foundry_endpoint,
    # e.g. https://tyndale-dev-foundry.services.ai.azure.com). Both default off so
    # nothing changes until the Foundry resources are provisioned (enable_foundry)
    # AND this is flipped on. Deployments are named after the model ids by default,
    # so foundry_model() is identity unless FOUNDRY_DEPLOYMENT_* override the names.
    use_foundry: bool = False
    foundry_endpoint: str | None = None
    # Entra token audience for keyless inference. Runtime-configurable via
    # FOUNDRY_TOKEN_SCOPE (Terraform sets it). Canonical Azure AI Services audience.
    # HISTORY: https://ai.cognitiveservices.com/.default (what MS's Foundry how-to
    # shows) was REJECTED with `invalid_scope` 400 by the Container Apps
    # managed-identity token endpoint on 2026-07-04 — do not use it. The remaining
    # alternate if this value ever fails auth is https://ai.azure.com/.default.
    foundry_token_scope: str = "https://cognitiveservices.azure.com/.default"
    foundry_deployment_sonnet: str | None = None
    foundry_deployment_haiku: str | None = None

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
    # base64 image in a JSON body (insurance card upload, CO-18). base64 of a 10 MB
    # image is ~13.3 MB; 15 MB leaves headroom. The route enforces the real 10 MB
    # per-image limit on the DECODED bytes.
    max_upload_body_bytes: int = 15 * 1024 * 1024  # 15 MB — base64-image JSON bodies
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
    # DL-04 crisis screen. When true (default), chat ingress attempts the Haiku
    # classifier and degrades to the deterministic keyword screen without usable
    # creds; when false, the keyword screen is the only layer. Either way the
    # screen never fails open (a positive → clean Category-2 decline).
    use_real_crisis_classifier: bool = True

    # Tighter knob: when use_real_claude is true but ANTHROPIC_API_KEY is unset
    # (e.g. running locally without creds), the agents fall back to fixtures
    # rather than raising. Defaults False (CO-15) — a prod deploy must NEVER
    # silently serve the MRI fixture as a real audit; see assert_production_safety().
    allow_fixture_fallback: bool = False

    # DL-88 — surprise-billing / No Surprises Act checks. Default FALSE until the
    # 50-state + DC seed passes its retrieval gate (check_state_seed.py, DL-81):
    # applying NSA/state balance-billing rules against an incomplete jurisdiction
    # seed would state protections the corpus can't actually ground. Dormant for
    # now; the audit provenance names it when a regime would need those checks.
    enable_nsa_checks: bool = False
    # DL-89 — CPT/NCCI/MUE code→description display + code-backed checks. Default
    # FALSE until the AMA CPT license is executed (Brock owns). DL-54 already keeps
    # AMA-copyrighted descriptors out of user surfaces; this gates turning code
    # display on at all once the license lands.
    enable_cpt_display: bool = False

    # DL-55/56 — appeals case management stays SHADOW-MODE. Sprint G builds the appeal
    # clocks + escalation state machine but keeps them dark (no user-facing surfaces;
    # admin read-only) until this flag is flipped per environment.
    enable_appeals_casemgmt: bool = False
    # Nudge emails for open load-bearing data-fetch items (Sprint G). Default FALSE so no
    # email sends without an explicit per-env opt-in; the scan + idempotency run regardless.
    enable_nudge_emails: bool = False
    # Nudge cadence: first at +3 days, second at +14 days, then in-app resurfacing only.
    nudge_first_days: int = 3
    nudge_second_days: int = 14

    def foundry_model(self, model_id: str) -> str:
        """Map an Anthropic model id to its Foundry deployment name. Deployments are
        named after the model ids by default (infra/envs/dev/ai_foundry.tf), so this
        is identity unless FOUNDRY_DEPLOYMENT_SONNET/HAIKU name them differently."""
        mid = (model_id or "").lower()
        if "haiku" in mid and self.foundry_deployment_haiku:
            return self.foundry_deployment_haiku
        if ("sonnet" in mid or "opus" in mid) and self.foundry_deployment_sonnet:
            return self.foundry_deployment_sonnet
        return model_id

    def resolved_model(self, model_id: str) -> str:
        """The model string to pass to the client: the Foundry deployment name when
        routing through Foundry, else the Anthropic model id unchanged. Every call
        site that names a model funnels through here so Foundry vs Anthropic-direct
        stays a one-switch decision."""
        return self.foundry_model(model_id) if self.use_foundry else model_id

    def claude_model_for(self, role: str) -> str:
        """Resolve the Claude model for a given role.

        Roles: 'lead_planner' | 'bill_detective' | 'math_person'.
        Falls back to claude_default_model_sonnet for the V1-Lite trio per D3.
        Under Foundry, resolves further to the deployment name (resolved_model).
        """
        override = getattr(self, f"claude_model_{role}_override", None)
        base = override or self.claude_default_model_sonnet
        return self.resolved_model(base)

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
        # Audit-log encryption: without a key, PostToolUse payloads are stored as
        # clear-text JSON (see app/security/audit_crypto.py). Warn loudly in prod.
        if not (self.audit_log_enc_key or "").strip():
            log.warning(
                "config.audit_log_unencrypted",
                var="AUDIT_LOG_ENC_KEY",
                note="audit payloads stored as clear-text JSON — set a base64 32-byte key",
            )

    def assert_production_safety(self) -> None:
        """Fail-fast guard (CO-15 / CO-18): a production deploy must never silently
        serve fixtures, and must never route PHI to Anthropic-direct. In production,
        ``allow_fixture_fallback`` MUST be False, ``use_real_claude`` MUST be True
        (else a missing/invalid key returns the MRI fixture as a real audit), and
        ``use_foundry`` MUST be True (DL-79 — Claude goes through the Azure Foundry
        BAA path via managed identity, not the Anthropic-direct dev/emergency
        fallback). Called from main.py's lifespan so an unsafe prod config fails to
        boot. The dev env runs NODE_ENV=development, so this is inert there until a
        real production profile stands up."""
        if not self.is_production:
            return
        problems: list[str] = []
        if self.allow_fixture_fallback:
            problems.append("ALLOW_FIXTURE_FALLBACK must be false in production")
        if not self.use_real_claude:
            problems.append("USE_REAL_CLAUDE must be true in production")
        if not self.use_foundry:
            problems.append(
                "USE_FOUNDRY must be true in production — Claude must route through the "
                "Azure Foundry BAA path (managed identity), not Anthropic-direct (DL-79)"
            )
        if not self.use_real_auth:
            problems.append(
                "USE_REAL_AUTH must be true in production — the dev seeded-admin stub "
                "(no sign-in required) must never run in prod"
            )
        if not self.use_real_ocr:
            problems.append(
                "USE_REAL_OCR must be true in production — real Document Intelligence, "
                "not the deterministic OCR stub"
            )
        if problems:
            raise RuntimeError("Unsafe production config — " + "; ".join(problems))

    def warn_disabled_real_flags(self) -> None:
        """Log a WARNING in ANY env for real-path flags that are off, so a dev/staging env
        states plainly that it is running a stub. In production these are hard errors
        (assert_production_safety); everywhere else they are just loud. Called from main.py's
        lifespan unconditionally."""
        if not self.use_real_auth:
            log.warning(
                "config.flag_disabled",
                flag="USE_REAL_AUTH",
                effect="auth uses the seeded-admin stub (no real sign-in)",
            )
        if not self.use_real_ocr:
            log.warning(
                "config.flag_disabled",
                flag="USE_REAL_OCR",
                effect="OCR uses the deterministic stub (no Document Intelligence)",
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
