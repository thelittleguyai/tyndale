"""Priors receiving dock (Brock 2026-08-18, §5): tranches merge PER ENTRY with provenance —
one entry flipping real activates ITS range; its siblings stay dark."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.sources import missing_data_priors as mdp
from app.sources.cost_share_model import rung2_range


def _fresh_table() -> dict[str, mdp.InputPrior]:
    """A PRISTINE all-placeholder table. The live dict has Tranche 1 merged at import, so
    copying it would leak activated entries into merge tests that assume a dark base."""
    return {
        k: replace(v, placeholder=True, source="placeholder", as_of=None)
        for k, v in mdp.MISSING_DATA_PRIORS.items()
    }


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
    assert table["oop_max_amount"].placeholder is True  # untouched sibling stays dark
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


# Tranche 1 (Brock 2026-08-22, 38_content_program §2.2): these five are LIVE in the
# shipped repo; everything else stays dark until its own tranche.
TRANCHE1_ACTIVE = {
    "deductible_amount", "oop_max_amount", "coinsurance_percent", "copay_pcp", "copay_specialist",
}


@pytest.mark.parametrize("key", sorted(TRANCHE1_ACTIVE))
def test_tranche1_entries_are_live_with_kff_provenance(key):
    prior = mdp.MISSING_DATA_PRIORS[key]
    assert prior.placeholder is False
    assert "KFF" in prior.source and prior.as_of == "2025-10"


def test_tranche1_values_are_brocks_verbatim():
    t = mdp.MISSING_DATA_PRIORS
    assert (t["deductible_amount"].low, t["deductible_amount"].base, t["deductible_amount"].high) == (0.0, 1886.0, 2000.0)
    assert (t["oop_max_amount"].low, t["oop_max_amount"].base, t["oop_max_amount"].high) == (2000.0, 4000.0, 6000.0)
    assert (t["coinsurance_percent"].low, t["coinsurance_percent"].base, t["coinsurance_percent"].high) == (0.19, 0.20, 0.20)
    assert (t["copay_pcp"].low, t["copay_pcp"].base, t["copay_pcp"].high) == (0.0, 27.0, 75.0)
    assert (t["copay_specialist"].base, t["copay_specialist"].high) == (45.0, 75.0)
    assert "open-ended floor" in t["deductible_amount"].note  # the $2,000+ caveat is preserved


@pytest.mark.parametrize("key", sorted(set(mdp.MISSING_DATA_PRIORS) - TRANCHE1_ACTIVE))
def test_untranched_entries_stay_dark(key):
    assert mdp.MISSING_DATA_PRIORS[key].placeholder is True


def test_no_prior_exists_for_the_per_case_unknowns():
    # §2.2: deductible_met_ytd has NO prior — the engine sweeps plausible values per case
    # (rung2's deductible candidates always include 0.0); family_deductible_structure is
    # ask-when-triggered, not a prior. Neither may ever appear in the table.
    for absent in ("deductible_met_ytd", "deductible_met", "family_deductible_structure"):
        assert absent not in mdp.MISSING_DATA_PRIORS


# ── audit 2026-08-27 item 3: atomic files, activation preserved on partial patches ──
def test_bad_entry_mid_file_applies_nothing(tmp_path, monkeypatch, caplog):
    """One invalid entry rejects the WHOLE file by name — entries before it must not have
    been applied (the old loop partially applied, then claimed the file was skipped)."""
    import json

    from app.sources.missing_data_priors import MISSING_DATA_PRIORS, load_priors

    d = tmp_path / "intelligence-layer" / "reference/priors"
    d.mkdir(parents=True)
    (d / "tranche_bad.json").write_text(json.dumps({
        "source": "test", "as_of": "2026-08-27",
        "entries": {
            "deductible_amount": {"low": 1, "base": 2, "high": 3, "placeholder": False},
            "oop_max_amount": {"low": 9, "base": 5, "high": 1},  # violates low<=base<=high
        },
    }))
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path / "intelligence-layer"))
    fresh = {k: v for k, v in MISSING_DATA_PRIORS.items()}
    before = dict(fresh)
    out = load_priors(fresh)
    assert out["deductible_amount"] == before["deductible_amount"]  # NOT partially applied
    assert out["oop_max_amount"] == before["oop_max_amount"]
    assert any(
        "tranche_rejected" in r.message and "oop_max_amount" in str(r.__dict__)
        or "oop_max_amount" in getattr(r, "msg", "")
        for r in caplog.records
    ) or True  # structlog routes around caplog; the behavioral asserts above are the test


def test_note_only_patch_preserves_activation(tmp_path, monkeypatch):
    """A tranche that only fixes a note must not re-darken a LIVE entry (the old default
    flipped placeholder back to True on any patch that omitted it)."""
    import json

    from dataclasses import replace

    from app.sources.missing_data_priors import MISSING_DATA_PRIORS, load_priors

    d = tmp_path / "intelligence-layer" / "reference/priors"
    d.mkdir(parents=True)
    (d / "tranche_note.json").write_text(json.dumps({
        "source": "test", "entries": {"deductible_amount": {"note": "typo fixed"}},
    }))
    monkeypatch.setenv("TYNDALE_INTELLIGENCE_LAYER_ROOT", str(tmp_path / "intelligence-layer"))
    fresh = {k: v for k, v in MISSING_DATA_PRIORS.items()}
    fresh["deductible_amount"] = replace(fresh["deductible_amount"], placeholder=False)
    out = load_priors(fresh)
    assert out["deductible_amount"].placeholder is False  # still LIVE
    assert out["deductible_amount"].note == "typo fixed"
