"""rerank instruction loading honors TYNDALE_INTELLIGENCE_LAYER_ROOT (Phase 2.5).

Regression: the deployed container lays intelligence-layer at a path that differs from
runtime/../intelligence-layer, so rerank must respect the override env var (like
context_loader) instead of a hardcoded parents[3] path — else per-collection rerank
instructions silently fail to load in prod.
"""

from __future__ import annotations

from app.knowledge import rerank


def test_instructions_load_from_env_override(monkeypatch, tmp_path):
    layer = tmp_path / "il"  # a non-default (container-style) layout
    (layer / "collections").mkdir(parents=True)
    (layer / "collections" / "rerank_instructions.md").write_text(
        "## billing_codes\nRank CPT/HCPCS matches by code specificity.\n\n"
        "## laws_regulations\nPrefer the controlling statute.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(layer))
    rerank._instructions.cache_clear()
    try:
        assert (
            rerank.default_instruction("billing_codes")
            == "Rank CPT/HCPCS matches by code specificity."
        )
        assert rerank.default_instruction("laws_regulations") == "Prefer the controlling statute."
        assert rerank.default_instruction("nonexistent") is None
    finally:
        rerank._instructions.cache_clear()  # don't leak the fake into other tests


def test_instructions_empty_when_root_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path / "nope"))
    rerank._instructions.cache_clear()
    try:
        assert rerank.default_instruction("billing_codes") is None
    finally:
        rerank._instructions.cache_clear()
