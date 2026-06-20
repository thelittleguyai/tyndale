"""Placeholder adapters for the two interfaces whose engines land later.

AccumulatorSource — deterministic accumulator reconstruction (CO-12B).
ClinicalEncounterSource — shim over the Phase-2I line-item data (CO-12D).

They register so the seam resolves today, returning an explicit "not yet
available" result with confidence 0.0. The AccumulatorSource placeholder still
honors the DL-69 contract that accumulator Provenance carries a non-null
``as_of`` (it echoes the requested date), so the contract is exercised before the
real engine exists.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from app.schemas.provenance import Provenance
from app.sources.base import AccumulatorResult, EncounterResult


class PlaceholderAccumulator:
    """Implements AccumulatorSource (structural / Protocol). Engine: CO-12B."""

    adapter_name = "PlaceholderAccumulator"

    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult:
        # DL-69: accumulator Provenance MUST carry a non-null as_of. Echo the
        # requested date so the contract holds even though the engine is a stub.
        as_of_dt = datetime(as_of.year, as_of.month, as_of.day)
        return AccumulatorResult(
            data={"status": "not_available", "deductible_applied": None, "oop_applied": None},
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="computed",
                as_of=as_of_dt,
                confidence=0.0,
                assumptions=["deterministic accumulator engine lands in CO-12B"],
            ),
        )


class PlaceholderClinicalEncounter:
    """Implements ClinicalEncounterSource (structural / Protocol). Shim: CO-12D."""

    adapter_name = "PlaceholderClinicalEncounter"

    async def get_encounter(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> EncounterResult:
        return EncounterResult(
            data={
                "status": "not_available",
                "date_of_service": None,
                "reason": None,
                "line_items": [],
            },
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="user_upload",
                as_of=None,
                confidence=0.0,
                assumptions=["clinical-encounter shim over Phase-2I data lands in CO-12D"],
            ),
        )


if TYPE_CHECKING:
    from app.sources.base import AccumulatorSource, ClinicalEncounterSource

    _a: AccumulatorSource = PlaceholderAccumulator()  # structural-conformance (mypy)
    _e: ClinicalEncounterSource = PlaceholderClinicalEncounter()
