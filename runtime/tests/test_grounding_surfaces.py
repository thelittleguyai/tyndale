"""Grounding surfaces — E4/H3 source line + E3 gap callout.

These are doctrine, not decoration: the grounding doctrine says every claim is grounded, and
until now the user could not SEE that — a grounded finding and an ungrounded one rendered
identically. The load-bearing assertion is that a finding can NEVER render bare.
"""

from __future__ import annotations

import pytest

from app.agents.grounding import finding_source_line, gap_callout, resolve_source
from app.schemas.case_file import Citation, FindingOut


def _finding(**kw) -> FindingOut:
    base = dict(
        finding_id="f1", finding_type="payer_side", category="bundling",
        subagent_source="bill_detective", voice_tier="A", facts={},
    )
    base.update(kw)
    return FindingOut(**base)


# --- E4/H3: a finding can never render bare ---------------------------------
def test_citation_is_the_most_authoritative_source():
    f = _finding(
        citations=[Citation(authority="NCCI edit table 2026", src_id="s1", marker="[NCCI, src_1]")],
        legal_claim={"citation": "45 CFR 147"},
        facts={"source": "the bill"},
    )
    assert resolve_source(f) == "NCCI edit table 2026"  # citation wins


def test_legal_claim_then_facts_are_the_fallbacks():
    assert resolve_source(_finding(legal_claim={"source": "42 USC 1395"})) == "42 USC 1395"
    assert resolve_source(_finding(facts={"basis": "your plan documents"})) == "your plan documents"


def test_the_subagent_is_never_treated_as_a_source():
    """Who computed something is not evidence FOR it — a finding whose only provenance is the
    agent that produced it is unsourced, and must say so."""
    f = _finding(subagent_source="math_person")
    assert resolve_source(f) is None
    line, has_source = finding_source_line(f)
    assert has_source is False
    assert "can't point to a source" in line


def test_source_line_always_renders_one_of_the_two_states():
    """The invariant the UI depends on: sourced line OR explicit no-source state — never
    nothing, so a bare claim is structurally impossible."""
    for f in (
        _finding(citations=[Citation(authority="published rates", src_id="s", marker="[rates, src_2]")]),
        _finding(legal_claim={"citation": "NSA §2799B-3"}),
        _finding(facts={"source": "your EOB"}),
        _finding(),  # nothing resolvable
    ):
        line, has_source = finding_source_line(f)
        assert line and line.strip(), "a finding must never render without a grounding line"
        assert "{" not in line  # no raw slot leaked
        if has_source:
            assert line.startswith("source:")


def test_api_stamps_the_line_onto_every_finding():
    """The schema guarantees it, so a client can't omit it by accident."""
    from app.agents.orchestrator import _with_source_line

    f = _with_source_line(_finding(citations=[Citation(authority="CMS PFS 2026", src_id="s", marker="[PFS, src_3]")]))
    assert f.source_line == "source: CMS PFS 2026" and f.has_source is True

    bare = _with_source_line(_finding())
    assert bare.source_line and bare.has_source is False


# --- E3: the gap callout, and the zero-gap suppression ----------------------
def test_gap_callout_states_the_computed_gap():
    out = gap_callout(1184.60, 612.40)
    assert out == "**$572.20** less than your insurer's number"


@pytest.mark.parametrize(
    ("eob", "computed"),
    [(612.40, 612.40), (500.0, 900.0), (0.0, 0.0), (None, 612.40), (612.40, None)],
)
def test_no_callout_when_there_is_no_gap_to_claim(eob, computed):
    """The clean-bill variant problem: no zero-gap string exists, so render NO callout rather
    than "$0.00 less". A negative gap (we compute MORE than the insurer) is never dressed up
    as a saving either."""
    assert gap_callout(eob, computed) is None


def test_callout_never_leaks_a_raw_slot():
    assert "{" not in (gap_callout(1000.0, 100.0) or "")
