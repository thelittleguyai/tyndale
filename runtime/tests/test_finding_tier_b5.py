"""B5 (Brock 2026-08-18): the [A]/[B] finding split — citation enforcement goes LIVE.

fact → no chip · rule_based + cited → chip · rule_based uncited → degrades (never a bare
legal claim, never a crash) · §12.1 handoff is [B] with {program_source} as its citation.
"""

from __future__ import annotations

from app.agents.context_loader import DOCTRINE_VIOLATIONS, orchestration_step
from app.agents.grounding import apply_finding_tier, finding_source_line, finding_tier
from app.schemas.case_file import Citation, FindingOut


def _finding(**kw) -> FindingOut:
    base = dict(
        finding_id="f1", finding_type="payer_side", category="cost_share",
        subagent_source="math_person", voice_tier="A", facts={},
    )
    base.update(kw)
    f = FindingOut(**base)
    f.source_line, f.has_source = finding_source_line(f)
    return f


def test_fact_finding_no_chip():
    f = apply_finding_tier(_finding(facts={"gap": 120.0, "basis": "the EOB's arithmetic"}))
    assert f.tier == "fact"
    assert f.has_source is True  # still grounded (E4) — just rendered WITHOUT a chip


def test_rule_based_with_citation_gets_chip():
    f = apply_finding_tier(_finding(
        citations=[Citation(authority="No Surprises Act §2799A-1", src_id="s1", marker="[NSA, s1]")],
        legal_claim={"claim": "balance billing is barred here"},
    ))
    assert f.tier == "rule_based" and f.has_source is True
    assert "No Surprises Act" in f.source_line


def test_rule_based_uncited_degrades_and_is_counted():
    before = DOCTRINE_VIOLATIONS["rule_based_uncited:cost_share"]
    f = apply_finding_tier(_finding(legal_claim={"claim": "the plan must cover this"}))
    assert f.tier == "rule_based"
    assert f.has_source is False  # the [B] degradation path: honest no-source, never bare
    assert f.source_line  # never empty
    assert DOCTRINE_VIOLATIONS["rule_based_uncited:cost_share"] == before + 1


def test_tier_is_server_derived_from_shape():
    assert finding_tier(_finding()) == "fact"
    assert finding_tier(_finding(legal_claim={"citations": []})) == "fact"  # empty claim shell
    assert finding_tier(_finding(legal_claim={"source": "42 USC 1395"})) == "rule_based"


def test_handoff_is_b_tier_cited_renders_uncited_degrades():
    cited = orchestration_step(
        "handoff.generic_program",
        citation={"source": "42 CFR 460"}, program_name="PACE", program_source="42 CFR 460",
    )
    assert "PACE" in cited and "42 CFR 460" in cited and "keep your case open" in cited.lower()
    before = DOCTRINE_VIOLATIONS["b_without_citation:handoff.generic_program"]
    degraded = orchestration_step("handoff.generic_program", program_name="PACE", program_source=None)
    assert "PACE" not in degraded  # never a sourceless program claim
    assert DOCTRINE_VIOLATIONS["b_without_citation:handoff.generic_program"] == before + 1
