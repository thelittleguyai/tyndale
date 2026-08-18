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


# Rung-2 (2026-08-18): DELIBERATE placeholders — the unlock-more voice state is Brock's to
# author (asks §3.11), and the staging boot block is the forcing function. When he authors
# them, empty this set and restore the zero-placeholder assertions below.
DELIBERATE_PLACEHOLDERS = {"unlock_more.intro", "unlock_more.item_hint"}


def test_placeholders_are_exactly_the_section_311_set():
    """The zero-placeholder milestone (content drop, item 1) holds for every key EXCEPT the
    two §3.11 unlock-more seeds — pinned exactly, both directions: a stray new placeholder
    fails here, and Brock authoring §3.11 fails here too (the reminder to empty the set)."""
    offenders = sorted(k for k, v in load_orchestration_script().items()
                       if v.strip().startswith(PLACEHOLDER_PREFIX))
    assert offenders == sorted(DELIBERATE_PLACEHOLDERS), (
        f"placeholder set drifted from the deliberate §3.11 set: {offenders}"
    )


def test_staging_boot_blocks_on_exactly_the_311_keys():
    """The forcing function, proven live: staging refuses to boot NAMING the unlock-more
    keys — and nothing else."""
    import pytest

    with pytest.raises(RuntimeError, match="unlock_more.intro") as exc:
        Settings(node_env="staging").assert_production_safety()
    assert "unlock_more.item_hint" in str(exc.value)


def test_staging_boots_once_the_311_keys_are_authored(monkeypatch):
    """The original milestone, preserved by simulation: with the two seeds authored, staging
    boots clean again — Brock's copy drop is the ONLY thing between here and staging."""
    from app.agents import context_loader

    authored = dict(load_orchestration_script())
    for key in DELIBERATE_PLACEHOLDERS:
        assert key in authored
        authored[key] = '[A] "authored stand-in"'
    # The safety check imports load_orchestration_script from context_loader at call time,
    # so patching the module attribute is the whole simulation.
    monkeypatch.setattr(context_loader, "load_orchestration_script", lambda: authored)
    Settings(node_env="staging").assert_production_safety()


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
    Settings(node_env="staging").assert_production_safety()
