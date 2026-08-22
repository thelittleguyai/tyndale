"""Pytest fixtures.

Uses the configured Postgres (DATABASE_URL) with a NullPool engine + a dependency
override, which keeps connections from being reused across pytest-asyncio event
loops. Tables are created once at import (idempotent with the Alembic migration).
"""

from __future__ import annotations

import asyncio
import os

# Defaults for local dev so the suite runs without an .env file present.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://tyndale:tyndale@127.0.0.1:5432/tyndale")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("NODE_ENV", "development")
# Phase 2K.2: rate limiting OFF by default so the broader suite (which fires many
# requests) isn't throttled. test_hardening.py turns it on per-test.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# CO-15: allow_fixture_fallback now defaults FALSE (production safety — a missing
# key must never silently serve the MRI fixture). The suite runs without real
# Anthropic creds, so it opts into the fixture fallback explicitly here; NODE_ENV
# is development, so the prod-safety assertion is a no-op. Tests that assert the
# raise / prod-assertion paths set this off per-test.
os.environ.setdefault("ALLOW_FIXTURE_FALLBACK", "true")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db.models  # noqa: E402,F401  — register tables on Base.metadata
from app.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402

_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_session():
    async with _Session() as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session


def _init_db() -> None:
    async def _go() -> None:
        async with _engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await conn.run_sync(Base.metadata.create_all)
            # create_all never ALTERs an already-existing table, so a dev's persisted test DB
            # can carry a stale status CHECK after a constraint grows values (CI starts fresh, so
            # this is a no-op there). Re-apply the two status checks that have grown over time
            # (case_files: audit_incomplete; cron_run_log: interrupted) so the suite matches the
            # models. Additive supersets — every existing row already satisfies them.
            await conn.execute(
                text("ALTER TABLE case_files DROP CONSTRAINT IF EXISTS ck_case_files_status")
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD CONSTRAINT ck_case_files_status CHECK (status IN "
                    "('open','in_progress','encounter_verification_pending','encounter_verified',"
                    "'awaiting_eob_confirmation','audit_running','audit_complete','audit_incomplete',"
                    "'extraction_failed','not_a_bill','resolved','archived','attest_declined'))"
                )
            )
            # New nullable columns added after the table first existed on a dev's persisted DB.
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS "
                    "audit_incomplete_reason text"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS "
                    "soft_deleted_at timestamptz"
                )
            )
            await conn.execute(
                text("ALTER TABLE case_files ADD COLUMN IF NOT EXISTS soft_deleted_by uuid")
            )
            # 0042 (create_all won't ALTER a persisted dev DB — the 0041 lesson).
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                    "email_notifications_enabled boolean NOT NULL DEFAULT true"
                )
            )
            # 0043 — profile state + optional address.
            for ddl in (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS state varchar(2)",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line1 text",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS address_line2 text",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS city text",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS zip_code varchar(10)",
            ):
                await conn.execute(text(ddl))
            # 0044 — secondary insurance (role column + constraint swaps).
            for ddl in (
                "ALTER TABLE insurance_info ADD COLUMN IF NOT EXISTS "
                "role text NOT NULL DEFAULT 'primary'",
                "ALTER TABLE insurance_info DROP CONSTRAINT IF EXISTS uq_insurance_info_user",
                "ALTER TABLE insurance_info DROP CONSTRAINT IF EXISTS "
                "uq_insurance_info_user_role",
                "ALTER TABLE insurance_info ADD CONSTRAINT uq_insurance_info_user_role "
                "UNIQUE (user_id, role)",
                "ALTER TABLE insurance_info DROP CONSTRAINT IF EXISTS ck_insurance_info_role",
                "ALTER TABLE insurance_info ADD CONSTRAINT ck_insurance_info_role "
                "CHECK (role IN ('primary', 'secondary'))",
                "ALTER TABLE insurance_cards DROP CONSTRAINT IF EXISTS "
                "ck_insurance_cards_card_type",
                "ALTER TABLE insurance_cards ADD CONSTRAINT ck_insurance_cards_card_type "
                "CHECK (card_type IN ('front', 'back', 'secondary_front', 'secondary_back'))",
            ):
                await conn.execute(text(ddl))
            await conn.execute(
                text(
                    "ALTER TABLE case_files DROP CONSTRAINT IF EXISTS "
                    "ck_case_files_audit_incomplete_reason"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD CONSTRAINT ck_case_files_audit_incomplete_reason "
                    "CHECK (audit_incomplete_reason IS NULL OR audit_incomplete_reason IN "
                    "('needs_documents','system_error'))"
                )
            )
            await conn.execute(
                text("ALTER TABLE cron_run_log DROP CONSTRAINT IF EXISTS ck_cron_run_log_status")
            )
            await conn.execute(
                text(
                    "ALTER TABLE cron_run_log ADD CONSTRAINT ck_cron_run_log_status CHECK (status "
                    "IN ('running','success','failed','partial','interrupted'))"
                )
            )
            # Chat-first typed thread entries (DL-91): kind + payload on a persisted DB.
            await conn.execute(
                text(
                    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS kind text NOT NULL "
                    "DEFAULT 'message'"
                )
            )
            await conn.execute(
                text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS payload jsonb")
            )
            # 0046 — tap-to-reply chips (2026-08-22).
            await conn.execute(
                text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS suggested_replies jsonb")
            )
            await conn.execute(
                text("ALTER TABLE messages DROP CONSTRAINT IF EXISTS ck_messages_kind")
            )
            await conn.execute(
                text(
                    "ALTER TABLE messages ADD CONSTRAINT ck_messages_kind CHECK (kind IN "
                    "('message','status_card_update','system_message','moment_card',"
                    "'verification_request','verification_suggestion','attest_request'))"
                )
            )
            # Typed call identifiers (delta B4, migration 0037).
            for _col in ("claim_number", "account_number", "provider_phone", "payer_phone"):
                await conn.execute(
                    text(f"ALTER TABLE case_files ADD COLUMN IF NOT EXISTS {_col} text")
                )
            # Bridge marker uniqueness (migration 0039) — the DB half of thread idempotency.
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_conversation_marker "
                    "ON messages (conversation_id, (payload->>'marker')) "
                    "WHERE payload->>'marker' IS NOT NULL"
                )
            )
            # Anonymous analytics path (migration 0041) — user_id nullable on a persisted DB.
            await conn.execute(
                text("ALTER TABLE analytics_events ALTER COLUMN user_id DROP NOT NULL")
            )
            # Recovery-email stamp (§10.4, migration 0040).
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS "
                    "recovery_email_sent_at timestamptz"
                )
            )
            # Audit-ready email idempotency stamp (D3, migration 0038).
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS "
                    "audit_ready_email_sent_at timestamptz"
                )
            )
            # Attest-and-proceed spine (§A2 state 1, migration 0036).
            await conn.execute(
                text("ALTER TABLE case_files ADD COLUMN IF NOT EXISTS patient_name text")
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD COLUMN IF NOT EXISTS attest_status text "
                    "NOT NULL DEFAULT 'not_required'"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files DROP CONSTRAINT IF EXISTS ck_case_files_attest_status"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE case_files ADD CONSTRAINT ck_case_files_attest_status CHECK "
                    "(attest_status IN ('not_required','required','attested','declined'))"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS "
                    "ck_audit_events_event_type"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE audit_events ADD CONSTRAINT ck_audit_events_event_type CHECK "
                    "(event_type IN ('tool_invocation','subagent_call','model_call','user_action',"
                    "'system_action','hook_invocation','phi_block','attestation','access_request'))"
                )
            )
            # plan_types v2 (Brock 2026-07-06): reconcile coverage_regime 7→14 on a persisted DB +
            # add coverage_attributes. Convert any stale v1 rows first so the new CHECK holds.
            from app.plan_types import PLAN_TYPES as _PT

            _regime_in = ", ".join(f"'{t}'" for t in _PT)
            _renames = {
                "commercial": "state_regulated_commercial", "medicaid": "medicaid_ffs",
                "tricare_va": "tricare", "dual_qmb": "dual_eligible",
            }
            for _tbl in ("case_files", "insurance_info"):
                ck = f"ck_{_tbl}_coverage_regime"
                await conn.execute(text(f"ALTER TABLE {_tbl} DROP CONSTRAINT IF EXISTS {ck}"))
                for _old, _new in _renames.items():
                    await conn.execute(
                        text(
                            f"UPDATE {_tbl} SET coverage_regime = '{_new}' "
                            f"WHERE coverage_regime = '{_old}'"
                        )
                    )
                await conn.execute(
                    text(
                        f"ALTER TABLE {_tbl} ADD CONSTRAINT {ck} CHECK "
                        f"(coverage_regime IS NULL OR coverage_regime IN ({_regime_in}))"
                    )
                )
                await conn.execute(
                    text(f"ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS coverage_attributes jsonb")
                )
        await _engine.dispose()

    asyncio.run(_go())


_init_db()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine():
    """Dispose the app's engine after each test.

    Routes/orchestrator/tools use app.db.base.AsyncSessionLocal (the default-
    pool engine) directly, not the NullPool dependency override above.
    pytest-asyncio gives each test its own event loop, so a pooled connection
    opened in one test's loop is bound to that (now-closed) loop and explodes
    with 'RuntimeError: Event loop is closed' when the next test reuses it.
    Disposing after each test forces a fresh connection bound to the next
    test's loop. Test-only — no production impact.
    """
    yield
    from app.db.base import engine as app_engine

    await app_engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_access_request_limiter():
    """The access-request per-IP window (LOW-14) is process-local and every test shares one
    fake client IP — without a reset, unrelated tests posting the intake route would start
    429ing once five had run in one process."""
    from app.auth.rate_limit import access_request_limiter

    access_request_limiter.reset()
    yield
    access_request_limiter.reset()


@pytest.fixture
def real_orchestration_script(monkeypatch, tmp_path):
    """A non-placeholder orchestration script (DL-91). A complete staging/production config needs
    real authored copy, so prod-safety tests request this to represent one.

    It used to seed ONE key, which stopped representing a real script when the render-path
    manifest landed: a genuine drop carries every key the thread bridge renders, and a boot now
    fails without them. Seeding the manifest keeps this fixture's promise true — and means a
    test that uses it is asserting against something a real deploy could actually be."""
    from app.agents.context_loader import load_orchestration_script
    from app.agents.thread_bridge import RENDER_PATH_KEYS

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    body = "".join(f"## {key}\n\nAuthored copy for {key}.\n\n" for key in sorted(RENDER_PATH_KEYS))
    (prompts / "orchestration_script.md").write_text(
        f"---\nversion: 1.0.0\n---\n\n## acknowledgment\n\nGot your documents.\n\n{body}"
    )
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    load_orchestration_script.cache_clear()
    yield
    load_orchestration_script.cache_clear()
