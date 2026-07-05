"""Disclosure tier flows through the audit payload (Sprint C, DL-85): the orchestrator
computes it deterministically from coverage completeness + cross-validation, and BOTH the
real assembly path and the fixture path emit the same Disclosure shape."""

from __future__ import annotations

from app.agents.orchestrator import _compute_disclosure
from app.stubs.fixtures import mri_audit_fixture

_COMPLETE = {"deductible_amount": 2000, "oop_max_amount": 8000, "coinsurance_percent": 0.2}


def test_missing_cost_share_inputs_trigger_chase():
    d = _compute_disclosure({}, cross_validation_material=False)
    assert d.tier == 3
    assert d.label == "chase"
    # The wide-dollar priors are chaseable; coinsurance (a fraction) is not.
    assert "deductible_amount" in d.chase_inputs
    assert "oop_max_amount" in d.chase_inputs
    assert "coinsurance_percent" not in d.chase_inputs
    assert set(d.missing_inputs) == {"deductible_amount", "oop_max_amount", "coinsurance_percent"}


def test_complete_inputs_are_grounded():
    d = _compute_disclosure(_COMPLETE, cross_validation_material=False)
    assert d.tier == 0
    assert d.label == "grounded"
    assert d.chase_inputs == []
    assert d.missing_inputs == []


def test_cross_validation_material_forces_disclose():
    d = _compute_disclosure(_COMPLETE, cross_validation_material=True)
    assert d.tier == 2
    assert d.label == "disclose"
    assert d.chase_inputs == []


def test_fixture_path_emits_disclosure_shape():
    result = mri_audit_fixture("11111111-1111-1111-1111-111111111111")
    assert result.disclosure is not None
    assert result.disclosure.tier == 0
    assert result.disclosure.label == "grounded"
