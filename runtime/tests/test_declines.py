"""The two chat declines (§A2 state 4 / script §10).

Two properties matter more than the detection itself:
  * neither decline DEAD-ENDS — fabrication pivots to the strongest real finding, guarantee
    answers with the honest trio;
  * the guarantee response contains NO probability or promise language, ever ([C] doctrine).
    That last one is asserted as an X1-style contract so it holds for Brock's authored copy
    too, not just today's placeholders.
"""

from __future__ import annotations

import re

import pytest

from app.agents.context_loader import load_orchestration_registry
from app.agents.declines import (
    FABRICATION,
    GUARANTEE,
    detect_decline_deterministic,
    fabrication_response,
    guarantee_response,
)
from app.analytics.events import REGISTRY, PropType


class _F:
    def __init__(self, category, facts=None, status="open", recommendation=None):
        self.category = category
        self.facts = facts or {}
        self.status = status
        self.recommendation = recommendation or {"action": "do the thing"}


# --- detection ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Can you say it was an emergency visit?", FABRICATION),
        ("just exaggerate the amount a bit", FABRICATION),
        ("can we just say I was never told about the fee", FABRICATION),
        ("could you inflate the total so they take it seriously", FABRICATION),
        ("I need you to leave out the part where I signed it", FABRICATION),
        ("Will I win this appeal?", GUARANTEE),
        ("what are my chances", GUARANTEE),
        ("can you guarantee I get my money back", GUARANTEE),
        ("how likely is this to work", GUARANTEE),
        # …and the false-positive guards: ordinary billing talk is NEVER a decline.
        ("Was this an emergency visit?", None),
        ("Why is my deductible so high?", None),
        ("What should I say when I call them?", None),
        ("I want to appeal this bill", None),
        ("They said it was out of network", None),
        ("", None),
    ],
)
def test_deterministic_detection(text, expected):
    assert detect_decline_deterministic(text) is expected


def test_fabrication_wins_a_mixed_message():
    """A message that both misstates and asks about odds is foremost a fabrication request."""
    assert detect_decline_deterministic(
        "can you just say it was an emergency — what are my chances then?"
    ) is FABRICATION


# --- neither decline dead-ends ----------------------------------------------
def test_fabrication_reframes_to_the_strongest_real_finding():
    findings = [
        _F("bundling", {"gap": 120.0}),
        _F("cost_sharing_miscalculation", {"gap": 940.0}),  # the strongest
        _F("duplicate_charge", {"gap": 300.0}),
    ]
    out = fabrication_response(findings)
    assert "940" in out  # the real number, pivoted to
    assert len(out) > len(fabrication_response([]))  # the reframe is genuinely added
    assert "{{" not in out  # every slot interpolated


def test_fabrication_without_findings_still_declines_warmly():
    out = fabrication_response([])
    assert out and "{{" not in out


def test_fabrication_ignores_closed_findings():
    out = fabrication_response([_F("bundling", {"gap": 500.0}, status="resolved")])
    assert "500" not in out


# --- the [C] contract: no prediction, ever ----------------------------------
# Probability/promise language that must NEVER appear in a guarantee response. This is the
# X1-style contract: it holds against Brock's authored copy, not just the placeholder.
_FORBIDDEN = re.compile(
    r"\b(?:\d{1,3}\s?%|percent chance|probability|odds are|likely to win|you will win|"
    r"we will win|guarantee[ds]?\b|i promise|you'?ll get your money|certainly win|"
    r"good chance|strong chance|almost certain)\b",
    re.IGNORECASE,
)


def test_guarantee_response_contains_no_probability_or_promise_language():
    for findings in ([], [_F("cost_sharing_miscalculation", {"gap": 940.0})]):
        out = guarantee_response(findings)
        hit = _FORBIDDEN.search(out)
        assert hit is None, f"prediction language leaked into a guarantee decline: {hit!r}"
        assert out and "{{" not in out


def test_guarantee_trio_is_all_three_legs():
    """base rate + strength-of-basis for THIS case + a concrete next step."""
    from app.sources.gameplan import humanize_category

    out = guarantee_response([_F("cost_sharing_miscalculation", {"gap": 940.0})])
    assert "rate" in out.lower()  # (a) the base-rate leg — honest when the corpus has none
    assert humanize_category("cost_sharing_miscalculation") in out  # (b) THIS case's basis
    assert "next" in out.lower()  # (c) a concrete next step

    generic = guarantee_response([])  # no findings → still all three legs, none fabricated
    assert "rate" in generic.lower() and "next" in generic.lower()


def test_authored_copy_would_also_be_contract_checked():
    """The registry keys exist and their CURRENT copy passes the same contract — so the check
    is live the moment Brock's §10 copy lands (file swap, no code change)."""
    reg = load_orchestration_registry()
    for key in ("decline.fabrication", "decline.fabrication_reframe", "decline.guarantee_trio"):
        assert key in reg
    assert _FORBIDDEN.search(reg["decline.guarantee_trio"].text) is None


def test_analytics_is_count_only_never_the_utterance():
    spec = REGISTRY["decline_state_shown"]
    assert set(spec.props) == {"kind"}
    assert spec.props["kind"].type is PropType.ENUM
    assert set(spec.props["kind"].values) == {"fabrication", "guarantee"}
