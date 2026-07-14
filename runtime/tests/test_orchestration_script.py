"""Orchestration-script loader + the staging/production placeholder guard (D1, DL-91).

The chat-first thread renders system copy from intelligence-layer/prompts/orchestration_script.md
verbatim. Engineering seeds [PLACEHOLDER-eng] values for dev; a staging/production boot must FAIL
while any active value still carries that prefix (Brock's authored copy hasn't landed yet)."""

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
    assert all(v.startswith(PLACEHOLDER_PREFIX) for v in s.values())  # all seeded as placeholders


def test_interpolation_and_missing_fallback():
    assert "a bill and an EOB" in orchestration_step("acknowledgment", doc_types="a bill and an EOB")
    # a missing key is explicit + testable, never a silent empty string
    assert orchestration_step("does_not_exist") == "<MISSING-script: does_not_exist>"


def test_loader_missing_file_degrades_to_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))  # no script file here
    load_orchestration_script.cache_clear()
    try:
        assert load_orchestration_script() == {}
    finally:
        load_orchestration_script.cache_clear()


def test_dev_boot_ignores_placeholders():
    Settings(node_env="development").assert_production_safety()  # inert in dev


def test_staging_boot_fails_on_placeholder_copy():
    with pytest.raises(RuntimeError, match="PLACEHOLDER-eng"):
        Settings(node_env="staging").assert_production_safety()


def test_authored_copy_passes_staging(monkeypatch, tmp_path):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "orchestration_script.md").write_text(
        "---\nversion: 1.0.0\n---\n\n## acknowledgment\n\nGot your documents.\n"
    )
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    load_orchestration_script.cache_clear()
    try:
        Settings(node_env="staging").assert_production_safety()  # real copy → boots clean
    finally:
        load_orchestration_script.cache_clear()
