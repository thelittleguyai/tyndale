"""Case-file / audit response shapes, including the three-number audit."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThreeNumberAudit(BaseModel):
    """The Independent Audit Doctrine's three numbers."""

    provider_billed: float = Field(description="What the provider billed")
    eob_member_responsibility: float = Field(
        description="What the payer's EOB claims the member owes"
    )
    tyndale_computed: float = Field(
        description="What Tyndale independently computes the member should owe"
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
    # Item 1 — why an audit_incomplete result stopped: budget_exceeded | no_three_number_finding
    # | error. None on a complete run. The frontend renders the honest terminal state from it.
    incomplete_reason: str | None = None
