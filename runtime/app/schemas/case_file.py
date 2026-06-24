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


class AuditResult(BaseModel):
    case_file_id: str
    status: str
    # None on a degraded "audit_incomplete" result: real agents ran but produced
    # no three-number finding. We never present {0,0,0} as a completed audit (CO-15).
    audit: ThreeNumberAudit | None = None
    findings: list[FindingOut]
    summary: str
