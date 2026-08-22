"""Case-file / audit response shapes, including the three-number audit."""

from __future__ import annotations

from pydantic import BaseModel, Field


def as_dict(value: object) -> dict | None:
    """Defensive read of an agent-written open-object column (facts / legal_claim /
    recommendation). Agents store free-form JSON; the literal STRING 'null' has occurred
    live (2026-08-19 dev sweep: deductible_misapplied's recommendation), and any non-dict
    value 500s the strict FindingOut — or AttributeErrors every `(x or {}).get(...)`
    reader, since a non-empty string is truthy. Anything that isn't a dict reads as
    absent; the row itself is preserved for diagnosis."""
    return value if isinstance(value, dict) else None


class ThreeNumberAudit(BaseModel):
    """The Independent Audit Doctrine's three numbers.

    Rung-2 completion (2026-08-18, the SBC-gate removal): an audit with missing coverage
    terms COMPLETES with `tyndale_computed` as the priors-swept range's base and
    `tyndale_computed_low/high` bracketing it (X3 tier ≥2 renders the range form). An
    anchor a document never stated is None — a bill-only case has no EOB number to show,
    and showing one would fabricate it. `computed_source` says who produced the number:
    the Math Person agent, or the deterministic rung-2 engine."""

    provider_billed: float | None = Field(None, description="What the provider billed")
    eob_member_responsibility: float | None = Field(
        None, description="What the payer's EOB claims the member owes"
    )
    tyndale_computed: float = Field(
        description="What Tyndale independently computes the member should owe"
    )
    tyndale_computed_low: float | None = Field(
        None, description="Range floor when coverage inputs are missing (X3 range form)"
    )
    tyndale_computed_high: float | None = Field(
        None, description="Range ceiling when coverage inputs are missing (X3 range form)"
    )
    computed_source: str = Field(
        "agent", description="'agent' (Math Person) | 'engine_rung2' (deterministic model)"
    )
    currency: str = "USD"


class Citation(BaseModel):
    authority: str
    section: str | None = None
    src_id: str
    marker: str = Field(description="Inline citation marker, e.g. '[ACA §2713, src_0a1b2c3d]'")


class FindingOut(BaseModel):
    finding_id: str
    finding_type: str = Field(description="payer_side | provider_side | encounter_mismatch")
    category: str
    subagent_source: str
    voice_tier: str = Field(description="A | B | C")
    facts: dict
    legal_claim: dict | None = None
    recommendation: dict | None = None
    citations: list[Citation] = Field(default_factory=list)
    # B5 (Brock 2026-08-18) — the [A]/[B] finding split, derived SERVER-SIDE in
    # grounding.finding_tier and never by a client: 'rule_based' when the finding rests on
    # a law / regulation / plan provision (a legal_claim or citations), 'fact' for
    # arithmetic and direct-observation findings. Rendering rule: fact → NO citation chip
    # (chips on arithmetic teach users to ignore chips); rule_based → chip REQUIRED —
    # cited renders the chip, uncited renders the [B] degradation line and is counted.
    tier: str = "fact"
    # E4/H3 — the VISIBLE half of the grounding doctrine. Always populated: either the
    # resolved "source: …" line or the explicit no-source state, never nothing. A client
    # therefore cannot render a bare claim even by omission.
    source_line: str = ""
    has_source: bool = False
    # X5 — the typed error taxonomy (DRAFT pending Brock, packet A6). Derived at the read seam
    # from doctrine_config's unambiguous category maps when upstream didn't assert one; the
    # escape hatch carries the category as its sub-label. None on informational findings.
    # error_type_source says which: "upstream" (asserted) vs "derived_draft" (our mapping).
    error_type: str | None = None
    error_type_sub_label: str | None = None
    error_type_source: str | None = None
    # X2 — explicit informational typing; upstream doesn't write it yet (the informational
    # CATEGORIES stand in per doctrine_config), but the field exists so it can.
    presentation: str | None = None


class AuditProvenance(BaseModel):
    """Sprint B (DL-82): the coverage-regime context an audit ran under, so nothing
    silently pretends. For any non-commercial (or unconfirmed) regime the audit still
    runs the generic path but carries an explicit assumption naming the pending
    population-specific corpus."""

    coverage_regime: str | None = None
    regime_verified: bool = False
    assumptions: list[str] = Field(default_factory=list)


class Disclosure(BaseModel):
    """Deterministic disclosure tier (Sprint C, DL-85). The audit's confidence is a
    function of the data, never the model's self-report:
      0 grounded · 1 note · 2 disclose · 3 chase (ask the user for a document).
    ``chase_inputs`` are the missing inputs whose plausible span crosses USER_CHASE — the
    dashboard renders a 'please find this document' card when the tier is 3."""

    tier: int = 0
    label: str = "grounded"
    missing_inputs: list[str] = Field(default_factory=list)
    chase_inputs: list[str] = Field(default_factory=list)


class EobCompletenessOut(BaseModel):
    """The 'does that look like all of them?' summary (Sprint D, DL-86). ``confirmed`` is
    null until the user answers; the audit treats totals as complete only when true."""

    eob_count: int
    plan_year: int | None = None
    date_start: str | None = None
    date_end: str | None = None
    dated_count: int = 0
    undated_count: int = 0
    patient_names: list[str] = Field(default_factory=list)
    covers_family: bool = False
    confirmed: bool | None = None
    question: str = ""


class EobConfirmRequest(BaseModel):
    all_uploaded: bool


class DocumentNeed(BaseModel):
    """One item on the 'to finish your audit' checklist. PHI-free by construction — a document
    TYPE plus plain 'how to get it', never amounts/providers. `have` reflects the case's actual
    document inventory (True once the user has provided it and extraction succeeded), so the UI
    renders a real checked/unchecked state instead of guessing from an icon default."""

    key: str = Field(description="eob | itemized_bill | sbc")
    label: str
    how_to_get: str
    have: bool = Field(default=False, description="True if the case already has this document")


class AuditResult(BaseModel):
    case_file_id: str
    status: str
    # None on a degraded "audit_incomplete" result: real agents ran but produced
    # no three-number finding. We never present {0,0,0} as a completed audit (CO-15).
    audit: ThreeNumberAudit | None = None
    findings: list[FindingOut]
    summary: str
    # Sprint B: the regime the audit ran under + any generic-path assumptions.
    audit_provenance: AuditProvenance | None = None
    # Sprint C: the deterministic disclosure tier + any documents to chase.
    disclosure: Disclosure | None = None
    # Why an audit_incomplete case stopped (persisted on the case, read back here):
    #   'needs_documents' — user-actionable: findings produced, three-number blocked on missing
    #                       inputs. The app shows a POSITIVE "here's what we found; to finish we
    #                       need…" screen with documents_needed — never failure language.
    #   'system_error'    — not user-actionable: budget / citation gate / provider failure. The
    #                       app shows the apology copy; this is the ONLY case that legitimately
    #                       says "our team has been notified" (a structured alert is emitted).
    # None on a complete run.
    incomplete_reason: str | None = None
    # Populated only when incomplete_reason == 'needs_documents': the honest document checklist.
    documents_needed: list[DocumentNeed] = Field(default_factory=list)
