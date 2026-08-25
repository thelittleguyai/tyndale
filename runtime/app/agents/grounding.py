"""Grounding surfaces — the VISIBLE half of the grounding doctrine (conformance E4 / H3 / E3).

The doctrine says every claim is grounded in authoritative data. The engine already holds that
line; what was missing is that the user could not SEE it — findings rendered without a source
line, so a grounded claim and an ungrounded one looked identical on screen.

Two pure helpers:

  finding_source_line()  the "source: …" line for a finding, resolved from the most
                         authoritative artefact it carries, or None when nothing resolves —
                         in which case the caller MUST render the explicit no-source state.
                         A bare claim with neither is a doctrine violation, and the API
                         guarantees one or the other is always present.

  gap_callout()          the reveal's "{gap} less than your insurer's number" framing,
                         suppressed at a zero/negative gap (no zero-gap variant exists, and
                         "$0.00 less" reads worse than saying nothing).
"""

from __future__ import annotations

from typing import Any

from app.agents.context_loader import orchestration_step


def _first_str(*candidates: Any) -> str | None:
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None


def resolve_source(finding: Any) -> str | None:
    """The most authoritative source this finding can name, or None.

    Precedence mirrors the doctrine's "most authoritative + most specific available":
    an explicit citation beats a legal claim's own source, which beats a structured-fact
    provenance note. The subagent that produced it is NOT a source — who computed something
    is not evidence for it — so it is deliberately not a fallback here.
    """
    for c in getattr(finding, "citations", None) or []:
        get = c.get if isinstance(c, dict) else (lambda k, _c=c: getattr(_c, k, None))
        authority = _first_str(get("authority"))
        if authority:
            section = _first_str(get("section"))
            return f"{authority} {section}".strip() if section else authority

    legal = getattr(finding, "legal_claim", None)
    if isinstance(legal, dict):
        label = _first_str(legal.get("citation"), legal.get("source"), legal.get("authority"))
        if label:
            return label

    facts = getattr(finding, "facts", None)
    if isinstance(facts, dict):
        label = _first_str(facts.get("source"), facts.get("source_note"), facts.get("basis"))
        if label:
            return label
    return None


def finding_tier(finding: Any) -> str:
    """B5 (Brock 2026-08-18): 'rule_based' when the finding rests on a law / regulation /
    plan provision — it carries a legal_claim with substance or any citation — else 'fact'
    (arithmetic, direct observation). Server-derived; the client only renders it."""
    if getattr(finding, "citations", None):
        return "rule_based"
    lc = getattr(finding, "legal_claim", None)
    if isinstance(lc, dict) and any(
        isinstance(v, str) and v.strip() for k, v in lc.items() if k != "citations"
    ):
        return "rule_based"
    return "fact"


_RESPONSIBLE_PARTIES = ("provider", "payer", "either")
_PARTY_BY_FINDING_TYPE = {"payer_side": "payer", "provider_side": "provider"}


def derive_responsible_party(finding: Any) -> str:
    """Attribution (Brock 38 §3): an explicit facts.responsible_party — the value a matched
    rule carried — wins when valid; otherwise the finding_type maps (payer_side → payer,
    provider_side → provider, anything else → either). Server-derived, never the client."""
    facts = getattr(finding, "facts", None) or {}
    explicit = facts.get("responsible_party") if isinstance(facts, dict) else None
    if isinstance(explicit, str) and explicit in _RESPONSIBLE_PARTIES:
        return explicit
    return _PARTY_BY_FINDING_TYPE.get(getattr(finding, "finding_type", ""), "either")


def apply_finding_tier(finding: Any) -> Any:
    """Stamp the tier and enforce the chip rule. An UNCITED rule-based finding is the
    never-a-bare-legal-claim case: the source line becomes the honest no-source state
    (the existing [B] degradation path) and a doctrine violation is counted. Never a crash."""
    from app.agents.context_loader import DOCTRINE_VIOLATIONS

    finding.tier = finding_tier(finding)
    finding.responsible_party = derive_responsible_party(finding)
    if finding.tier == "rule_based" and not getattr(finding, "has_source", False):
        DOCTRINE_VIOLATIONS[f"rule_based_uncited:{getattr(finding, 'category', '?')}"] += 1
        finding.source_line, finding.has_source = orchestration_step("finding_no_source"), False
    return finding


def finding_source_line(finding: Any) -> tuple[str, bool]:
    """``(line, has_source)`` — ALWAYS a renderable line.

    ``has_source`` False means the honest no-source state was returned; the UI styles it
    differently (and never as a citation chip), but a finding is never left bare."""
    source = resolve_source(finding)
    if source:
        return orchestration_step("finding_card_source", finding_source=source), True
    return orchestration_step("finding_no_source"), False


def gap_callout(eob_member_responsibility: float | None, tyndale_computed: float | None) -> str | None:
    """E3 — the reveal's gap framing, or None when there is nothing to claim.

    Suppressed unless the gap is a real, positive amount: a clean bill (gap 0) must not render
    "$0.00 less than your insurer's number", and a NEGATIVE gap (we compute MORE than the
    insurer) is never dressed up as a saving."""
    if eob_member_responsibility is None or tyndale_computed is None:
        return None
    gap = round(eob_member_responsibility - tyndale_computed, 2)
    if gap <= 0:
        return None
    return orchestration_step("reveal.gap_callout", gap=f"${gap:,.2f}")
