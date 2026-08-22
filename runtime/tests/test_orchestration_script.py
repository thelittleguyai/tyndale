"""Orchestration-script loader + the staging/production placeholder guard (D1, DL-91).

The chat-first thread renders system copy from intelligence-layer/prompts/orchestration_script.md
verbatim. Brock's authored v1 has LANDED (docs/build-kit/33_orchestration_script.md), so the
registry is placeholder-free and the staging boot gate passes — these tests hold that line."""

from __future__ import annotations

import pytest

from app.agents.context_loader import (
    PLACEHOLDER_PREFIX,
    load_orchestration_script,
    orchestration_step,
)
from app.config import Settings

_PHASE_A_KEYS = (
    "acknowledgment", "stage_label_extraction", "stage_label_translate", "stage_label_encounter",
    "stage_label_audit", "verification_intro", "verification_nudge", "audit_start", "long_wait",
    "cap_collision", "needs_documents_intro", "needs_documents_item", "reaudit_announce",
    "three_number_reveal", "system_error", "completion",
)


def test_registry_parses_every_phase_a_key():
    s = load_orchestration_script()
    for k in _PHASE_A_KEYS:
        assert k in s, f"missing script key: {k}"
    assert "Variables" not in s  # the meta section is not parsed as a key


def test_interpolation_and_missing_fallback():
    # Brock's §1.4 variables ({doc_list} / {payer}); both single-brace, his convention.
    out = orchestration_step("acknowledgment", doc_list="a bill and an EOB", payer="Blue Shield")
    assert "a bill and an EOB" in out and "Blue Shield" in out
    # a missing key is explicit + testable, never a silent empty string
    assert orchestration_step("does_not_exist") == "<MISSING-script: does_not_exist>"


# v1.1 (Brock 2026-08-18 §1): the §3.11 unlock-more seeds are AUTHORED. The deliberate
# placeholder set is EMPTY again — the zero-placeholder milestone holds for every key, and
# the staging copy gates pass against the real registry (the staging-boot unblock).
DELIBERATE_PLACEHOLDERS: set[str] = set()


def test_no_placeholders_remain():
    """Zero placeholders, pinned both directions: a stray new [PLACEHOLDER-eng] fails here."""
    offenders = sorted(k for k, v in load_orchestration_script().items()
                       if v.strip().startswith(PLACEHOLDER_PREFIX))
    assert offenders == sorted(DELIBERATE_PLACEHOLDERS) == [], (
        f"placeholder copy in the registry: {offenders}"
    )


def test_staging_copy_gates_pass_against_the_real_registry():
    """THE STAGING-BOOT UNBLOCK (Brock 2026-08-18 §1): with §8.4/§8.5 authored, a staging
    boot passes BOTH copy gates — no placeholder copy, no missing render-path key — against
    the real registry, no simulation. (HIGH-1's auth/fixture asserts are satisfied
    explicitly so this stays about the copy gates.)"""
    Settings(
        node_env="staging", use_real_auth=True, allow_fixture_fallback=False
    ).assert_production_safety()  # no raise


def test_unlock_more_copy_is_brocks_verbatim():
    script = load_orchestration_script()
    assert script["unlock_more.intro"].startswith("That's your complete audit — every charge checked.")
    assert script["unlock_more.item_hint"] == (
        "Everything checked is already on file. Each unchecked one is optional — and adds "
        "something more I can verify."
    )


def test_crisis_copy_carries_no_resource_routing():
    """B1 (Brock 2026-08-18): DL-04 stands. The unwired §10.5 key is gone from the registry
    and the wired crisis path is still the clean decline — no resources, no routing."""
    from app.agents.chat import _CRISIS_DECLINE

    assert "crisis_care_first" not in load_orchestration_script()
    assert "resources" not in _CRISIS_DECLINE.lower()
    assert "attest.edge_substance" not in load_orchestration_script()  # A5


def test_loader_missing_file_degrades_to_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))  # no script file here
    load_orchestration_script.cache_clear()
    try:
        assert load_orchestration_script() == {}
    finally:
        load_orchestration_script.cache_clear()


def test_dev_boot_ignores_placeholders():
    Settings(node_env="development").assert_production_safety()  # inert in dev


def test_staging_boot_still_fails_if_placeholder_copy_returns(monkeypatch, tmp_path):
    """The gate itself must keep working — point the loader at a seeded file and it must fail."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "orchestration_script.md").write_text(
        f"---\nversion: 0.0.1\n---\n\n## acknowledgment\n\n{PLACEHOLDER_PREFIX} seeded.\n"
    )
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    load_orchestration_script.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="PLACEHOLDER-eng"):
            Settings(node_env="staging").assert_production_safety()
    finally:
        load_orchestration_script.cache_clear()


def test_authored_copy_passes_staging(real_orchestration_script):
    """A complete, placeholder-free drop boots staging clean.

    Uses the shared fixture rather than its own one-key file: since the render-path manifest
    landed, "authored copy" means every key the bridge renders is present, and a stub with one
    key would assert a weaker thing than the name promises."""
    Settings(
        node_env="staging", use_real_auth=True, allow_fixture_fallback=False
    ).assert_production_safety()
