"""Placeholder adapter for the interface whose engine lands later.

ClinicalEncounterSource — shim over the Phase-2I line-item data (CO-12D).

(CO-12A also shipped a PlaceholderAccumulator; CO-12B replaced it with the real
ComputedFromUploadedEOBs + EOBStatedYTD engine.)

It registers so the seam resolves today, returning an explicit "not yet available"
result with confidence 0.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.provenance import Provenance
from app.sources.base import EncounterResult


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
    from app.sources.base import ClinicalEncounterSource

    _e: ClinicalEncounterSource = PlaceholderClinicalEncounter()  # structural-conformance (mypy)
