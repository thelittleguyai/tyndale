"""Regression tests for the 2026-08-19 security review's unilateral fixes.

One section per item, in the review's order. Each test pins the specific behavior the
review demanded, so a refactor that quietly regresses one fails with the item's name.
"""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def _settings(**over) -> Settings:
    base = {"database_url": "postgresql+asyncpg://u:p@localhost/db"}
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture
def real_auth(monkeypatch):
    """Real-auth flavor of the shared settings, mirroring tests/test_auth.py's fixture
    (kept local — conftest doesn't export it)."""
    from app.auth.rate_limit import magic_link_limiter

    s = get_settings()
    monkeypatch.setattr(s, "use_real_auth", True)
    monkeypatch.setattr(s, "auth_secret", "test-secret-key-for-jwt-hs256-32b!")
    monkeypatch.setattr(s, "cookie_domain", "")
    monkeypatch.setattr(s, "cookie_secure", False)
    magic_link_limiter.reset()
    yield s
    magic_link_limiter.reset()


# ── HIGH-1: the boot guard treats staging like production for auth + fixtures ───────


def test_high1_staging_with_stub_auth_refuses_to_boot(real_orchestration_script):
    s = _settings(node_env="staging", use_real_auth=False)
    with pytest.raises(RuntimeError, match="USE_REAL_AUTH"):
        s.assert_production_safety()


def test_high1_staging_with_fixture_fallback_refuses_to_boot(real_orchestration_script):
    s = _settings(node_env="staging", use_real_auth=True, allow_fixture_fallback=True)
    with pytest.raises(RuntimeError, match="ALLOW_FIXTURE_FALLBACK"):
        s.assert_production_safety()


def test_high1_safe_staging_config_boots(real_orchestration_script):
    s = _settings(node_env="staging", use_real_auth=True, allow_fixture_fallback=False)
    s.assert_production_safety()  # no raise


def test_high1_production_still_enforces_both(real_orchestration_script):
    # The checks moved tiers — production must not have LOST them in the refactor.
    s = _settings(
        node_env="production",
        use_real_claude=True,
        use_foundry=True,
        foundry_endpoint="https://x.services.ai.azure.com",
        use_real_ocr=True,
        use_real_auth=False,
        allow_fixture_fallback=True,
    )
    with pytest.raises(RuntimeError, match="USE_REAL_AUTH"):
        s.assert_production_safety()
    with pytest.raises(RuntimeError, match="ALLOW_FIXTURE_FALLBACK"):
        s.assert_production_safety()


def test_high1_development_still_boots_with_stubs():
    _settings(node_env="development", use_real_auth=False).assert_production_safety()


# ── MEDIUM-2: magic-link return_url is same-origin-relative or ignored ──────────────


def test_medium2_safe_return_path_matrix():
    from app.routes.auth import _safe_return_path

    assert _safe_return_path("/case/123") == "/case/123"
    assert _safe_return_path("/settings?tab=insurance") == "/settings?tab=insurance"
    assert _safe_return_path("https://evil.example/phish") is None  # absolute off-domain
    assert _safe_return_path("//evil.example") is None  # protocol-relative
    assert _safe_return_path("javascript:alert(1)") is None  # scheme, no leading /
    assert _safe_return_path("/\\evil.example") is None  # backslash → // after normalize
    assert _safe_return_path("/ok\r\nSet-Cookie: x") is None  # control chars
    assert _safe_return_path(None) is None
    assert _safe_return_path(123) is None


@pytest.mark.asyncio
async def test_medium2_hostile_return_url_falls_back_to_default(client, real_auth):
    # Minted directly with a hostile value — the already-issued-token case the consume-time
    # guard exists for (the mint path independently refuses to sign one).
    from app.auth.jwt import create_magic_link_token
    from app.config import get_settings

    token, _ = create_magic_link_token("redirectee@example.com", "https://evil.example/phish")
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == get_settings().auth_success_redirect


@pytest.mark.asyncio
async def test_medium2_relative_return_url_passes_through(client, real_auth):
    from app.auth.jwt import create_magic_link_token

    token, _ = create_magic_link_token("returner@example.com", "/case/123")
    r = await client.get(f"/v1/auth/magic-link-verify?token={token}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/case/123"
