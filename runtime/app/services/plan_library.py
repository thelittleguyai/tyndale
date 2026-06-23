"""PlanLibrary service (Phase CO-12C, DL-73) — match / propose / confirm / fork.

PLAN-LEVEL ONLY. ``strip_identifiers`` is the gating PHI rule: an ALLOWLIST that
keeps only benefit-design terms, so every identifier (member id, name, group,
subscriber, DOB, account/claim, address, free-text) AND every per-person amount
(*_met accumulator state) is dropped before anything is stored — even unknown
keys are dropped. Never carries a prior plan year forward without explicit
confirmation. A confirm increments the stored design's confidence; a reject FORKS
a new entry rather than overwriting. All confirmed coverage still lands in
CaseFile.coverage (the canonical store) — PlanLibrary only proposes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case_files import CaseFile
from app.db.models.plan_library import PlanLibraryEntry

# The ONLY keys allowed into a stored benefit_design — plan-level benefit terms.
# Everything else is dropped: identifiers (member_id/group/name/dob/account/claim/
# address), free-text, AND per-person accumulator state (deductible_met/oop_max_met).
# Allowlist (not denylist) => provably no PHI, even for keys we didn't anticipate.
BENEFIT_DESIGN_KEYS = frozenset(
    {
        "deductible_amount",
        "deductible_family",
        "deductible_out_of_network",
        "oop_max_amount",
        "oop_max_family",
        "oop_max_out_of_network",
        "coinsurance_percent",
        "coinsurance_out_of_network",
        "copay_pcp",
        "copay_specialist",
        "copay_er",
        "copay_urgent_care",
        "pcp_required",
        "prior_auth_required",
        "prior_auth_required_categories",
        "network_tier",
        "plan_type",
    }
)


def strip_identifiers(design: dict[str, Any] | None) -> dict[str, Any]:
    """Keep ONLY benefit-design keys; drop every identifier / per-person field.
    The gating PHI rule (DL-73)."""
    return {k: v for k, v in (design or {}).items() if k in BENEFIT_DESIGN_KEYS and v is not None}


async def match(
    session: AsyncSession,
    payer: str | None,
    plan_id: str | None,
    plan_name: str | None,
    plan_year: int | None,
) -> PlanLibraryEntry | None:
    """Best stored design for (payer, plan, year), or None. A plan_year mismatch is
    NEVER a match — a prior year is not carried forward silently."""
    if not payer or plan_year is None:
        return None
    rows = list(
        (
            await session.execute(
                select(PlanLibraryEntry).where(
                    func.lower(PlanLibraryEntry.payer) == str(payer).lower(),
                    PlanLibraryEntry.plan_year == int(plan_year),
                )
            )
        )
        .scalars()
        .all()
    )
    if plan_id:
        rows = [r for r in rows if r.plan_id == plan_id] or rows
    if plan_name:
        rows = [r for r in rows if (r.plan_name or "").lower() == str(plan_name).lower()] or rows
    return max(rows, key=lambda r: r.confidence) if rows else None


def propose(entry: PlanLibraryEntry) -> dict[str, Any]:
    """A one-tap-confirm payload for the UI propose-confirm path."""
    d = entry.benefit_design or {}
    bits: list[str] = []
    if d.get("deductible_amount") is not None:
        bits.append(f"deductible ${float(d['deductible_amount']):,.0f}")
    if d.get("copay_specialist") is not None:
        bits.append(f"specialist copay ${float(d['copay_specialist']):,.0f}")
    elif d.get("coinsurance_percent") is not None:
        bits.append(f"{float(d['coinsurance_percent']):.0f}% coinsurance")
    detail = ", ".join(bits) if bits else "your benefit design"
    name = entry.plan_name or entry.payer
    return {
        "plan_library_id": str(entry.plan_library_id),
        "payer": entry.payer,
        "plan_name": entry.plan_name,
        "plan_year": entry.plan_year,
        "benefit_design": dict(d),
        "confidence": entry.confidence,
        "summary": f"Looks like you're on {name} ({entry.plan_year}) — {detail}. Does this match?",
    }


def _pointer(entry: PlanLibraryEntry) -> dict[str, Any]:
    return {
        "plan_library_id": str(entry.plan_library_id),
        "payer": entry.payer,
        "plan_name": entry.plan_name,
        "plan_year": entry.plan_year,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }


async def confirm(session: AsyncSession, entry: PlanLibraryEntry, case: CaseFile) -> None:
    """Confirm a proposed design: write it into CaseFile.coverage (canonical store,
    same keys manual entry uses), point plan_current at the entry, and increment the
    library entry's confidence. Caller commits."""
    case.coverage = {**(case.coverage or {}), **strip_identifiers(entry.benefit_design)}
    case.plan_current = _pointer(entry)
    entry.confidence = (entry.confidence or 1) + 1


async def reject(
    session: AsyncSession,
    entry: PlanLibraryEntry,
    corrected_design: dict[str, Any] | None,
    case: CaseFile,
) -> PlanLibraryEntry:
    """Reject + correct: FORK a new (PHI-stripped) plan_library entry rather than
    overwriting; archive the prior pointer into plan_history; write the corrected
    design into coverage and point plan_current at the fork. Caller commits."""
    clean = strip_identifiers(corrected_design)
    fork = PlanLibraryEntry(
        plan_library_id=uuid4(),
        payer=entry.payer,
        plan_id=entry.plan_id,
        plan_name=entry.plan_name,
        plan_year=entry.plan_year,
        benefit_design=clean,
        confidence=1,
        source="user_confirmed",
    )
    session.add(fork)
    if case.plan_current:
        case.plan_history = [*(case.plan_history or []), case.plan_current]
    case.coverage = {**(case.coverage or {}), **clean}
    case.plan_current = _pointer(fork)
    return fork
