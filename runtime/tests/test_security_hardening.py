"""Regression tests for the 2026-08-19 security review's unilateral fixes.

One section per item, in the review's order. Each test pins the specific behavior the
review demanded, so a refactor that quietly regresses one fails with the item's name.
"""

from __future__ import annotations

import pytest

from app.config import Settings


def _settings(**over) -> Settings:
    base = {"database_url": "postgresql+asyncpg://u:p@localhost/db"}
    base.update(over)
    return Settings(**base)  # type: ignore[arg-type]


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
