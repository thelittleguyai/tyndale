"""Medicare participation — resolve, don't estimate (Brock 2026-08-22, §2.3).

Tier 0 by contract: participation is a mechanically checkable fact (the CMS opt-out NPI
dataset, Nov 2024 data), so it is RESOLVED silently and recorded internally — never
surfaced to the user as an assumption or a claim. Opt-out is rare (1.2% overall) but
concentrated by specialty (psychiatry 8.1%, plastic surgery 4.5%), so the resolver is
specialty-aware in how much confidence an unresolved lookup deserves.

The DATA is not ingested yet — resolve_participation runs against a pluggable source and
the shipped source is an honest stub that answers "unknown" for every NPI. Degradation is
the 98%-participating prior: treat as participating with an INTERNAL low-confidence flag.

TODO(ingestion): ingest the CMS opt-out affidavits file (Nov 2024) into a lookup table.
Cron-registry candidate: ``cms_optout_npi`` (quarterly refresh), alongside the
medicare_pfs/hospital_mrf crons in app/crons/registry.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# Internal risk-ranking constants ONLY (never user-facing): how concentrated opt-out is,
# per Brock's §2.3. Used to annotate an unresolved lookup's confidence, nothing else.
OPT_OUT_RATES: dict[str, float] = {
    "_overall": 0.012,
    "psychiatry": 0.081,
    "plastic surgery": 0.045,
}


class OptOutSource(Protocol):
    def is_opted_out(self, npi: str) -> bool | None:
        """True/False when the dataset answers; None when it cannot (not ingested,
        NPI absent, malformed)."""
        ...


class StubOptOutSource:
    """The shipped source until the CMS file is ingested: every lookup is 'unknown'."""

    def is_opted_out(self, npi: str) -> bool | None:  # noqa: ARG002 — interface parity
        return None


@dataclass(frozen=True)
class ParticipationResult:
    """Internal record — Tier 0, nothing here is user-facing."""

    participating: bool
    resolved: bool  # True = the dataset answered; False = the 98%-prior assumption
    confidence: str  # "resolved" | "assumed_low_confidence"
    source: str
    specialty_opt_out_rate: float


def resolve_participation(
    npi: str | None,
    specialty: str | None = None,
    source: OptOutSource | None = None,
) -> ParticipationResult:
    """Resolve silently; degrade honestly. Unresolvable → participating (the 98% prior)
    with an internal low-confidence flag — never surfaced to the user as a claim."""
    src = source or StubOptOutSource()
    rate = OPT_OUT_RATES.get((specialty or "").strip().lower(), OPT_OUT_RATES["_overall"])
    answer = src.is_opted_out(npi) if npi else None
    if answer is None:
        return ParticipationResult(
            participating=True,
            resolved=False,
            confidence="assumed_low_confidence",
            source="prior: 98% of clinicians participate (CMS opt-out file, Nov 2024 data)",
            specialty_opt_out_rate=rate,
        )
    return ParticipationResult(
        participating=not answer,
        resolved=True,
        confidence="resolved",
        source="CMS opt-out NPI dataset (Nov 2024 data)",
        specialty_opt_out_rate=rate,
    )
