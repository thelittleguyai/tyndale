"""BenefitsContext — pairs CoverageSource + AccumulatorSource behind one facade (DL-68).

They're read together (you need both the benefit design and how much has been
spent against it), a single vendor adapter answers both in one call, and the
three-way cross-validation — user-stated vs EOB-stated vs computed benefit
amounts — will live here in CO-12B. For now it simply delegates to the registry.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.sources.base import (
    AccumulatorResult,
    AccumulatorSource,
    CoverageResult,
    CoverageSource,
)
from app.sources.registry import SourceRegistry


class BenefitsContext:
    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry

    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult:
        return await self._registry.resolve(CoverageSource).get_coverage(case_file_id, args)

    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult:
        # TODO(CO-12B): cross-validate user-stated vs EOB-stated vs computed
        # benefit amounts here, where both interfaces are visible together.
        return await self._registry.resolve(AccumulatorSource).get_accumulator(
            case_file_id, as_of, args
        )
