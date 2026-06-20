"""app.sources — the four patient-data interfaces (DL-68) + Provenance (DL-69).

Importing this package wires the default SourceRegistry: each interface gets its
single CO-12A adapter —

    CoverageSource          -> UserUploadedSBC
    ClaimsSource            -> UserUploadedEOB
    AccumulatorSource       -> PlaceholderAccumulator        (engine: CO-12B)
    ClinicalEncounterSource -> PlaceholderClinicalEncounter  (shim:   CO-12D)

``resolve()`` / ``benefits_context`` read from that default registry; the
``upload_extract_{coverage,eob}`` tools call through it. Jonas's wrapper registers
OneUpHealth* / eligibility adapters into the same registry later, behind the same
interfaces, with zero agent change.
"""

from __future__ import annotations

from typing import Any

from app.sources.adapters.placeholders import (
    PlaceholderAccumulator,
    PlaceholderClinicalEncounter,
)
from app.sources.adapters.user_uploaded_eob import UserUploadedEOB
from app.sources.adapters.user_uploaded_sbc import UserUploadedSBC
from app.sources.base import (
    AccumulatorResult,
    AccumulatorSource,
    ClaimsResult,
    ClaimsSource,
    ClinicalEncounterSource,
    CoverageResult,
    CoverageSource,
    EncounterResult,
    SourceResult,
)
from app.sources.benefits_context import BenefitsContext
from app.sources.registry import SourceRegistry

_registry = SourceRegistry()
_registry.register_adapter(CoverageSource, UserUploadedSBC(), priority=100)
_registry.register_adapter(ClaimsSource, UserUploadedEOB(), priority=100)
_registry.register_adapter(AccumulatorSource, PlaceholderAccumulator(), priority=0)
_registry.register_adapter(ClinicalEncounterSource, PlaceholderClinicalEncounter(), priority=0)

#: Facade pairing CoverageSource + AccumulatorSource (DL-68).
benefits_context = BenefitsContext(_registry)


def get_registry() -> SourceRegistry:
    """The process-wide default SourceRegistry."""
    return _registry


def resolve(interface: type) -> Any:
    """Resolve the registered adapter for an interface from the default registry."""
    return _registry.resolve(interface)


__all__ = [
    "AccumulatorResult",
    "AccumulatorSource",
    "BenefitsContext",
    "ClaimsResult",
    "ClaimsSource",
    "ClinicalEncounterSource",
    "CoverageResult",
    "CoverageSource",
    "EncounterResult",
    "SourceRegistry",
    "SourceResult",
    "benefits_context",
    "get_registry",
    "resolve",
]
