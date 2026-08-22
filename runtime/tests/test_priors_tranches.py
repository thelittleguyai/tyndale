"""Priors receiving dock (Brock 2026-08-18, §5): tranches merge PER ENTRY with provenance —
one entry flipping real activates ITS range; its siblings stay dark."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.sources import missing_data_priors as mdp
from app.sources.cost_share_model import rung2_range


def _fresh_table() -> dict[str, mdp.InputPrior]:
    return {k: replace(v) for k, v in mdp.MISSING_DATA_PRIORS.items()}


def test_partial_tranche_merges_one_entry_with_provenance(tmp_path, monkeypatch):
    (tmp_path / "reference" / "priors").mkdir(parents=True)
    (tmp_path / "reference" / "priors" / "tranche_001.json").write_text(json.dumps({
        "source": "missing_data_spectrum_2026-08-20.md",
        "as_of": "2026-08-20",
        "entries": {
            "deductible_amount": {"low": 500, "base": 1700, "high": 6000, "placeholder": False,
                                  "note": "KFF 2025 individual deductible spread"},
            "not_a_real_input": {"low": 1, "base": 2, "high": 3},  # logged + ignored
        },
    }))
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    table = mdp.load_priors(_fresh_table())

    ded = table["deductible_amount"]
    assert ded.placeholder is False and ded.base == 1700.0 and ded.high == 6000.0
    assert ded.source == "missing_data_spectrum_2026-08-20.md" and ded.as_of == "2026-08-20"
    # Siblings untouched: still placeholders, still the engineering values, no provenance.
    assert table["coinsurance_percent"].placeholder is True
    assert table["coinsurance_percent"].as_of is None
    assert table["oop_max_amount"] == mdp.MISSING_DATA_PRIORS["oop_max_amount"]
    assert "not_a_real_input" not in table


def test_one_entry_flipping_real_activates_its_range_siblings_stay_dark(tmp_path, monkeypatch):
    (tmp_path / "reference" / "priors").mkdir(parents=True)
    (tmp_path / "reference" / "priors" / "t1.json").write_text(json.dumps({
        "as_of": "2026-08-20", "source": "tranche 1",
        "entries": {"deductible_amount": {"placeholder": False}},
    }))
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    table = mdp.load_priors(_fresh_table())
    monkeypatch.setattr(mdp, "MISSING_DATA_PRIORS", table)
    from app.sources import cost_share_model
    monkeypatch.setattr(cost_share_model, "MISSING_DATA_PRIORS", table)

    # Coverage states coinsurance, lacks the deductible → ONLY the deductible prior is swept.
    rng = rung2_range(1000.0, {"coinsurance_percent": 0.2}, anchor_kind="allowed")
    assert rng.placeholder_basis is False  # its range is LIVE
    assert rng.low < rng.high

    # A case missing the coinsurance instead → that sibling is still dark → range suppressed.
    rng2 = rung2_range(1000.0, {"deductible_amount": 500.0}, anchor_kind="allowed")
    assert rng2.placeholder_basis is True


def test_a_malformed_tranche_is_rejected_not_fatal(tmp_path, monkeypatch):
    (tmp_path / "reference" / "priors").mkdir(parents=True)
    (tmp_path / "reference" / "priors" / "bad.json").write_text("{not json")
    (tmp_path / "reference" / "priors" / "inverted.json").write_text(json.dumps({
        "entries": {"copay_er": {"low": 900, "base": 350, "high": 700, "placeholder": False}},
    }))
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    table = mdp.load_priors(_fresh_table())
    assert table["copay_er"].placeholder is True  # the inverted entry was rejected
    assert table["copay_er"].base == 350.0


def test_no_tranche_dir_means_everything_stays_dark(tmp_path, monkeypatch):
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path))
    table = mdp.load_priors(_fresh_table())
    assert all(p.placeholder for p in table.values())


@pytest.mark.parametrize("key", list(mdp.MISSING_DATA_PRIORS))
def test_live_table_is_still_all_placeholder_until_brocks_first_tranche(key):
    # The repo ships no tranche yet — nothing activates by accident.
    assert mdp.MISSING_DATA_PRIORS[key].placeholder is True
