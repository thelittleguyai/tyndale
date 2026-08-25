"""Regime-switchers are NOT priors (Brock 2026-08-22, §2.4) + the §2.3 silent resolutions.

A switcher flips WHICH RULES APPLY — a wrong silent default flips the case. None may
appear in the priors table or be swept by the range engine; each goes through the
verification ladder or an honest branch.
"""

from __future__ import annotations

import pytest

from app.sources.missing_data_priors import (
    MISSING_DATA_PRIORS,
    REQUIRED_COST_SHARE_INPUTS,
    missing_cost_share_inputs,
)

SWITCHERS = (
    "network_status",
    "coverage_population",
    "screening_vs_diagnostic",
    "nsa_plan_type",
    "emergency_status",
)


@pytest.mark.parametrize("key", SWITCHERS)
def test_switchers_are_never_priors_and_never_swept(key):
    assert key not in MISSING_DATA_PRIORS
    assert key not in REQUIRED_COST_SHARE_INPUTS
    # An empty coverage blob reports only the three cost-share inputs — never a switcher.
    assert key not in missing_cost_share_inputs({})


def test_coverage_population_goes_through_the_ladder_never_defaulted():
    """Ambiguous signals → a candidate to CONFIRM, verified stays False (the ladder);
    the regime is never silently asserted."""
    from app.sources.regime_detection import RegimeSignals, detect_regime

    det = detect_regime(RegimeSignals(payer_name="Acme Health"))
    assert det.verified is False


def test_grandfathered_is_a_detected_attribute_not_a_prior():
    """§2.3: assume non-grandfathered SILENTLY (no prior, no question); the SBC is checked
    silently when present — the mandated notice text sets the typed attribute."""
    from app.sources.regime_detection import RegimeSignals, detect_regime

    assert "grandfathered_status" not in MISSING_DATA_PRIORS
    assert "grandfathered" not in MISSING_DATA_PRIORS
    det = detect_regime(
        RegimeSignals(
            payer_name="Acme Health",
            document_text_blobs=["This plan carries the Notice of Grandfathered status."],
        )
    )
    assert det.attributes.get("grandfathered") is True
