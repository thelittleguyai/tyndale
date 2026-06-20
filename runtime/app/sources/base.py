"""The four patient-data interfaces (DL-68) + their typed result wrappers.

Agents (via tools) and future vendor wrappers read patient-specific data through
these four named Protocols — never a parser or vendor SDK directly:

  * CoverageSource          — benefit design (plan/payer/deductible/coinsurance/OOP)
  * AccumulatorSource       — amount spent toward deductible/OOP, as-of a date
  * ClinicalEncounterSource — visit date / reason / what was done
  * ClaimsSource            — billed-to-payer line data (the EOB)

Each method returns a small result carrying the existing domain payload (``data``)
PLUS a Provenance (DL-69). ``data`` reuses the EXACT dict shape the corresponding
tool already returns — no redesign. CoverageSource + AccumulatorSource are paired
behind BenefitsContext (they're read together; one vendor answers both).

Adapters register into a SourceRegistry (registry.py). Today each interface has
exactly one adapter (single-adapter passthrough); when a second registers, the
registry / BenefitsContext gain precedence + cross-validation (CO-12B) — agents
do not change.

NOTE (CO-12A transitional): the V1-Lite "now" adapters extract from an uploaded
document whose bytes arrive in the tool ``args`` (content_base64 / file_path).
The canonical handle is ``case_file_id`` (what OneUpHealth* / eligibility adapters
will use to look the case up); ``args`` is the optional V1-Lite upload payload.
Both are accepted so the existing upload-extract tools keep working byte-for-byte
while the seam is in place. A future adapter that loads by case_file_id ignores
``args``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, model_validator

from app.schemas.provenance import Provenance


class SourceResult(BaseModel):
    """A domain payload + its Provenance. ``data`` is the existing tool return
    shape (a plain dict), kept identical so downstream consumers are unaffected."""

    data: dict[str, Any]
    provenance: Provenance


class CoverageResult(SourceResult):
    """data == upload_extract_coverage's pre-CO-12A return:
    {coverage{...}, coverage_terms_confidence{...}, raw_ocr{...}}."""


class AccumulatorResult(SourceResult):
    """Accumulator figures (deductible / OOP applied), as-of a date.

    Per DL-69 the accumulator's Provenance MUST carry a non-null ``as_of`` —
    accumulator math is freshness-sensitive. Enforced here so a misbehaving
    adapter cannot ship freshness-blind accumulator data even before the real
    engine (CO-12B) exists."""

    @model_validator(mode="after")
    def _require_as_of(self) -> "AccumulatorResult":
        if self.provenance.as_of is None:
            raise ValueError("AccumulatorResult.provenance.as_of is required (DL-69)")
        return self


class EncounterResult(SourceResult):
    """Visit date / reason / line-item context. Real shim over Phase-2I data: CO-12D."""


class ClaimsResult(SourceResult):
    """data == upload_extract_eob's pre-CO-12A return: {eob{...}, raw_ocr{...}}."""


@runtime_checkable
class CoverageSource(Protocol):
    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult: ...


@runtime_checkable
class AccumulatorSource(Protocol):
    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult: ...


@runtime_checkable
class ClinicalEncounterSource(Protocol):
    async def get_encounter(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> EncounterResult: ...


@runtime_checkable
class ClaimsSource(Protocol):
    async def get_claims(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> ClaimsResult: ...
