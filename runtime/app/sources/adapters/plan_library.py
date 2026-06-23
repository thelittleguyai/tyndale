"""PlanLibrary — CoverageSource adapter (Phase CO-12C).

Returns the confirmed plan-level benefit design that landed in CaseFile.coverage via
the PlanLibrary propose/confirm path (app/services/plan_library.py), with
Provenance(adapter="PlanLibrary"). Registered BELOW UserUploadedSBC — resolve()
stays single-adapter passthrough (UserUploadedSBC remains primary); this adapter is
seam completeness so a confirmed design can be read through the CoverageSource
interface. The intake flow drives match/propose/confirm via the service, not here.
"""

from __future__ import annotations

from typing import Any

from app.schemas.provenance import Provenance
from app.services.plan_library import BENEFIT_DESIGN_KEYS
from app.sources.base import CoverageResult
from app.sources.case_data import load_case_coverage_and_plan


class PlanLibrary:
    """Implements CoverageSource (structural / Protocol)."""

    adapter_name = "PlanLibrary"

    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult:
        coverage, plan_current = await load_case_coverage_and_plan(case_file_id)
        coverage = coverage or {}
        design = {k: v for k, v in coverage.items() if k in BENEFIT_DESIGN_KEYS}
        confirmed = bool(plan_current and plan_current.get("plan_library_id"))
        return CoverageResult(
            data={
                "coverage": design,
                "coverage_terms_confidence": {
                    "overall": 0.85 if confirmed else 0.0,
                    "notes": (
                        "plan-level design confirmed via PlanLibrary"
                        if confirmed
                        else "no PlanLibrary design confirmed for this case"
                    ),
                },
            },
            provenance=Provenance(
                adapter=self.adapter_name,
                # A stored/confirmed design is 'computed'; a public_qhp source would be
                # 'public_data' (later). Not a user upload.
                source_kind="computed",
                as_of=None,
                confidence=0.85 if confirmed else 0.0,
                assumptions=[
                    "plan-level benefit design confirmed by the user via PlanLibrary"
                    if confirmed
                    else "no PlanLibrary design confirmed for this case"
                ],
            ),
        )
