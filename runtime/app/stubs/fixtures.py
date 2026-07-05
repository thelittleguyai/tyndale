"""Fixture data — the MRI scenario (simplified) from how_tyndale_works_reference.md.

Three numbers per the prompt: provider billed $1,200; the EOB claims the member
owes $1,200; Tyndale independently computes $560. One Tier B payer-side finding
with a PLACEHOLDER citation (authority + src_id) — real grounding lands in later
phases.
"""

from __future__ import annotations

from app.schemas.case_file import (
    AuditResult,
    Citation,
    Disclosure,
    FindingOut,
    ThreeNumberAudit,
)

# Stable id so the stub /v1/audit and tests can reference the same case.
MRI_CASE_FILE_ID = "00000000-0000-0000-0000-000000000001"

# Placeholder citation — NOT a real grounded source (Phase 5 ingests real law).
_PLACEHOLDER_CITATION = Citation(
    authority="PLACEHOLDER_AUTHORITY",
    section="§000",
    src_id="src_0a1b2c3d",
    marker="[PLACEHOLDER_AUTHORITY §000, src_0a1b2c3d]",
)


def mri_audit_fixture(case_file_id: str) -> AuditResult:
    audit = ThreeNumberAudit(
        provider_billed=1200.0,
        eob_member_responsibility=1200.0,
        tyndale_computed=560.0,
    )
    finding = FindingOut(
        finding_id="00000000-0000-0000-0000-0000000000f1",
        finding_type="payer_side",
        category="cost_sharing_miscalculation",
        subagent_source="math_person",
        voice_tier="B",
        facts={
            "provider_billed": 1200.0,
            "eob_member_responsibility": 1200.0,
            "tyndale_computed": 560.0,
            "gap": 640.0,
        },
        legal_claim={
            "claim": "The payer appears to have miscalculated member cost-sharing.",
            "marker": _PLACEHOLDER_CITATION.marker,
        },
        recommendation={
            "action": "Request a corrected EOB / call the payer to dispute the cost-sharing math.",
            "reasoning": "Tyndale's independent figure ($560) is $640 below the EOB's claimed $1,200.",
        },
        citations=[_PLACEHOLDER_CITATION],
    )
    return AuditResult(
        case_file_id=case_file_id,
        status="in_progress",
        audit=audit,
        findings=[finding],
        summary=(
            "Provider billed $1,200; the EOB claims you owe $1,200; Tyndale independently "
            "computes $560. The $640 gap is a payer-side cost-sharing miscalculation "
            "(Tier B, placeholder citation — STUB fixture)."
        ),
        # Complete-data fixture scenario → disclosure tier 0 (grounded), same shape as the
        # real path (Sprint C, DL-85).
        disclosure=Disclosure(tier=0, label="grounded"),
    )
