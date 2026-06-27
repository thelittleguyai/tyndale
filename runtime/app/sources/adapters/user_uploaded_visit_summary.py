"""UserUploadedVisitSummary — ClinicalEncounterSource shim over Phase-2I data (CO-12D).

The encounter data Tyndale has pre-FHIR is what the user gave us during encounter
verification (Phase 2I): Bill Detective's plain-language line-item translations, the
user's yes / no / not_sure confirmations, and their free-text visit context ("what
were you seen for"). This adapter exposes that through the ClinicalEncounterSource
interface so agents read the visit the same way a future OneUpHealthClinical adapter
will serve it — zero agent change when the FHIR clinical pull registers behind this
same Protocol.

NOT a clinical record: there is no coded date-of-service pre-FHIR, and the reason is
the user's own words, not a coded diagnosis. Both facts are recorded as Provenance
assumptions so a consumer never mistakes this for a chart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.schemas.provenance import Provenance
from app.sources.base import EncounterResult
from app.sources.case_data import load_case_encounter

# Modest confidence: the user's own account of the visit, verified line by line during
# encounter verification — not a clinical record.
_VISIT_SUMMARY_CONFIDENCE = 0.6


class UserUploadedVisitSummary:
    """Implements ClinicalEncounterSource (structural / Protocol). Shim over the
    Phase-2I encounter data persisted on CaseFile (CO-12D)."""

    adapter_name = "UserUploadedVisitSummary"

    async def get_encounter(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> EncounterResult:
        line_items, confirmations, visit_context = await load_case_encounter(case_file_id)
        has_data = bool(line_items or visit_context)
        return EncounterResult(
            data={
                "status": "available" if has_data else "not_available",
                "date_of_service": None,  # not captured pre-FHIR
                "reason": visit_context,  # the user's plain-language reason
                "line_items": line_items,  # what was billed, in plain language
                "confirmations": confirmations,  # what the user confirmed / denied
            },
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="user_upload",
                as_of=None,
                confidence=_VISIT_SUMMARY_CONFIDENCE if has_data else 0.0,
                assumptions=[
                    "date_of_service not captured pre-FHIR",
                    "user-reported visit context; not a clinical record",
                ],
            ),
        )


if TYPE_CHECKING:
    from app.sources.base import ClinicalEncounterSource

    _e: ClinicalEncounterSource = UserUploadedVisitSummary()  # structural-conformance (mypy)
