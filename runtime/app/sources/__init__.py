"""app.sources — the four patient-data interfaces (DL-68) + Provenance (DL-69).

Importing this package wires the default SourceRegistry: each interface gets its
registered adapter(s) —

    CoverageSource          -> UserUploadedSBC
    ClaimsSource            -> UserUploadedEOB
    AccumulatorSource       -> ComputedFromUploadedEOBs (priority 100, authoritative)
                               + EOBStatedYTD (priority 50, corroborating)   [CO-12B]
    ClinicalEncounterSource -> PlaceholderClinicalEncounter  (shim: CO-12D)

``resolve()`` stays single-adapter passthrough (returns the highest-priority
adapter). The accumulator's three-way cross-validation across both adapters + the
coverage-stated values is a BESPOKE step in BenefitsContext.get_accumulator (DL-72),
NOT a generic registry merge. Jonas's wrapper registers OneUpHealth* / eligibility
adapters into the same registry later, behind the same interfaces, with zero agent
change.
"""

from __future__ import annotations

from typing import Any

from app.sources.adapters.computed_from_uploaded_eobs import ComputedFromUploadedEOBs
from app.sources.adapters.eob_stated_ytd import EOBStatedYTD
from app.sources.adapters.placeholders import PlaceholderClinicalEncounter
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
# AccumulatorSource (CO-12B): the deterministic reconstruction is authoritative; the
# EOB-stated YTD is a corroborating reading for cross-validation (never adopted).
_registry.register_adapter(AccumulatorSource, ComputedFromUploadedEOBs(), priority=100)
_registry.register_adapter(AccumulatorSource, EOBStatedYTD(), priority=50)
_registry.register_adapter(ClinicalEncounterSource, PlaceholderClinicalEncounter(), priority=0)

#: Facade pairing CoverageSource + AccumulatorSource (DL-68); home of the three-way
#: accumulator cross-validation (DL-72).
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
