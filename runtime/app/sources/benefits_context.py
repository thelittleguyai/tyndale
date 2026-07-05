"""BenefitsContext — pairs CoverageSource + AccumulatorSource behind one facade
(DL-68) and is the home of the three-way accumulator cross-validation (DL-72).

``get_accumulator`` runs the deterministic ComputedFromUploadedEOBs (authoritative)
and the corroborating EOBStatedYTD, reads the user/card-stated coverage 'met' values,
and compares all three. Material disagreement -> ONE accumulator_discrepancy Finding
(Independent Audit Doctrine: the EOB's figure is never silently adopted). The
computed reconstruction is always returned as authoritative.

This is a BESPOKE doctrine step, not a generic merge: ``registry.resolve()`` stays
single-adapter passthrough (YAGNI per DL-68). We read both accumulator adapters via
``registry.adapters_for(AccumulatorSource)`` and the coverage-stated values directly
from the persisted case — no generic n>1 precedence engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from app.sources.base import (
    AccumulatorResult,
    AccumulatorSource,
    CoverageResult,
    CoverageSource,
)
from app.sources.case_data import as_float, load_case_eobs_coverage
from app.sources.materiality import AUDIT_FLAG, is_material
from app.sources.registry import SourceRegistry

# A finding writer persists a discrepancy spec. Injectable so unit tests can assert
# on emitted findings without a live DB; defaults to a real Finding row.
FindingWriter = Callable[[str, dict], Awaitable[None]]

# Cross-validation materiality (DL-72; $25 floor set by Brock 2026-06-26) now lives in
# app.sources.materiality.AUDIT_FLAG ($25 / 5% / $1 abs-tol) — the single home for the
# thresholds (DL-85). A gap is material per is_material(spread, base, AUDIT_FLAG).
_METRICS = ("deductible_applied", "oop_applied")


@dataclass
class CrossValidation:
    agreement: bool
    deltas: dict[str, Any]
    assumptions: list[str] = field(default_factory=list)
    finding_spec: dict | None = None


def cross_validate(
    computed: dict,
    eob_stated: dict,
    coverage_stated: dict,
    as_of: date,
    *,
    completeness_confirmed: bool | None = None,
) -> CrossValidation:
    """Pure three-way comparison of deductible_applied / oop_applied across the
    computed reconstruction, the EOB-stated YTD, and the user/card-stated coverage
    'met' values. Material disagreement -> a finding spec (computed stays the
    authoritative answer regardless). No I/O, no LLM.

    ``completeness_confirmed`` gates the 'corroborated/complete' branch (DL-86): agreeing
    readings are only called corroborated once the user has confirmed the EOB set is
    complete; otherwise the agreement is flagged provisional."""
    readings = {
        "computed": {m: as_float(computed.get(m)) for m in _METRICS},
        "eob_stated": {m: as_float(eob_stated.get(m)) for m in _METRICS},
        "coverage_stated": {
            "deductible_applied": as_float(coverage_stated.get("deductible_met")),
            "oop_applied": as_float(coverage_stated.get("oop_max_met")),
        },
    }
    deltas: dict[str, Any] = {}
    material = False
    for m in _METRICS:
        vals = {src: r[m] for src, r in readings.items() if r.get(m) is not None}
        if len(vals) >= 2:
            lo, hi = min(vals.values()), max(vals.values())
            spread = round(hi - lo, 2)
            base = max(abs(hi), abs(lo), 1.0)
            deltas[m] = {"spread": spread, "values": vals}
            if is_material(spread, base, AUDIT_FLAG):
                material = True

    if not material:
        if completeness_confirmed:
            note = "accumulator corroborated across the available readings"
        else:
            note = (
                "readings agree, but the EOB set is not confirmed complete — corroboration "
                "is provisional pending the completeness confirmation (DL-86)"
            )
        return CrossValidation(agreement=True, deltas=deltas, assumptions=[note])

    spec = {
        "finding_type": "payer_side",
        "category": "accumulator_discrepancy",
        "subagent_source": "math_person",
        "voice_tier": "A",
        "facts": {"readings": readings, "deltas": deltas, "as_of": as_of.isoformat()},
        "recommendation": {
            "action": (
                "Reconcile the accumulator: request a corrected EOB / member-portal "
                "accumulator readout and dispute the figure that disagrees with Tyndale's "
                "independent reconstruction."
            ),
            "reasoning": (
                "Tyndale computed the deductible/OOP met independently from the uploaded "
                "EOBs; it disagrees materially with the EOB-stated and/or card-stated figure. "
                "The discrepancy — not the payer's number — is the result."
            ),
        },
    }
    return CrossValidation(
        agreement=False,
        deltas=deltas,
        assumptions=[
            "accumulator readings disagree materially — see accumulator_discrepancy finding"
        ],
        finding_spec=spec,
    )


async def _default_finding_writer(case_file_id: str, spec: dict) -> None:
    """Persist a discrepancy spec as a Finding row (production path). Idempotent —
    one open accumulator_discrepancy per case. No-op for a non-case id."""
    try:
        cf_uuid = UUID(str(case_file_id))
    except (ValueError, AttributeError, TypeError):
        return
    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.db.models.findings import Finding

    async with AsyncSessionLocal() as s:
        existing = (
            await s.execute(
                select(Finding)
                .where(Finding.case_file_id == cf_uuid)
                .where(Finding.category == "accumulator_discrepancy")
                .where(Finding.status == "open")
            )
        ).first()
        if existing is not None:
            return
        s.add(
            Finding(
                finding_id=uuid4(),
                case_file_id=cf_uuid,
                finding_type=spec["finding_type"],
                category=spec["category"],
                subagent_source=spec["subagent_source"],
                voice_tier=spec["voice_tier"],
                facts=spec["facts"],
                recommendation=spec.get("recommendation"),
            )
        )
        await s.commit()


def _by_name(adapters: list[Any], name: str) -> Any | None:
    for a in adapters:
        if getattr(a, "adapter_name", None) == name:
            return a
    return None


class BenefitsContext:
    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry

    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult:
        return await self._registry.resolve(CoverageSource).get_coverage(case_file_id, args)

    async def get_accumulator(
        self,
        case_file_id: str,
        as_of: date,
        args: dict[str, Any] | None = None,
        *,
        finding_writer: FindingWriter | None = None,
    ) -> AccumulatorResult:
        """Computed reconstruction (authoritative) + three-way cross-validation. On
        material disagreement, writes ONE accumulator_discrepancy finding via
        ``finding_writer`` (defaults to a persisted Finding row)."""
        adapters = self._registry.adapters_for(AccumulatorSource)
        computed_adapter = _by_name(adapters, "ComputedFromUploadedEOBs") or self._registry.resolve(
            AccumulatorSource
        )
        eob_adapter = _by_name(adapters, "EOBStatedYTD")

        computed = await computed_adapter.get_accumulator(case_file_id, as_of, args)
        eob_stated = (
            await eob_adapter.get_accumulator(case_file_id, as_of, args) if eob_adapter else None
        )
        # User/card-stated reading: the PERSISTED coverage 'met' values (the stored
        # statement). Read directly — the V1-Lite CoverageSource adapter extracts from
        # upload bytes, which aren't present on this call path.
        _, coverage = await load_case_eobs_coverage(case_file_id)

        # DL-86: the persisted completeness flag gates the 'complete' branch below.
        completeness_confirmed = None
        if coverage and "all_plan_year_eobs_confirmed" in coverage:
            completeness_confirmed = bool(coverage["all_plan_year_eobs_confirmed"])
        cv = cross_validate(
            computed.data,
            eob_stated.data if eob_stated else {},
            coverage or {},
            as_of,
            completeness_confirmed=completeness_confirmed,
        )
        # Annotate the authoritative (computed) result with the cross-validation verdict.
        computed.provenance.assumptions = list(computed.provenance.assumptions) + cv.assumptions
        if cv.finding_spec is not None:
            await (finding_writer or _default_finding_writer)(case_file_id, cv.finding_spec)
        return computed  # computed reconstruction is authoritative; EOB-stated never adopted
