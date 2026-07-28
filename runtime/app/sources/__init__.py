"""app.sources — the four patient-data interfaces (DL-68) + Provenance (DL-69).

Importing this package wires the default SourceRegistry: each interface gets its
registered adapter(s) —

    CoverageSource          -> UserUploadedSBC (priority 100, primary)
                               + PlanLibrary (priority 50, confirmed design)   [CO-12C]
    ClaimsSource            -> UserUploadedEOB
    AccumulatorSource       -> ComputedFromUploadedEOBs (priority 100, authoritative)
                               + EOBStatedYTD (priority 50, corroborating)   [CO-12B]
    ClinicalEncounterSource -> UserUploadedVisitSummary  (shim over Phase-2I data: CO-12D)

``resolve()`` stays single-adapter passthrough (returns the highest-priority
adapter). The accumulator's three-way cross-validation across both adapters + the
coverage-stated values is a BESPOKE step in BenefitsContext.get_accumulator (DL-72),
NOT a generic registry merge. Jonas's wrapper registers OneUpHealth* / eligibility
adapters into the same registry later, behind the same interfaces, with zero agent
change.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings
from app.sources.adapters.computed_from_uploaded_eobs import ComputedFromUploadedEOBs
from app.sources.adapters.eob_stated_ytd import EOBStatedYTD
from app.sources.adapters.plan_library import PlanLibrary
from app.sources.adapters.user_uploaded_eob import UserUploadedEOB
from app.sources.adapters.user_uploaded_sbc import UserUploadedSBC
from app.sources.adapters.user_uploaded_visit_summary import UserUploadedVisitSummary
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

log = structlog.get_logger(__name__)

_registry = SourceRegistry()
_registry.register_adapter(CoverageSource, UserUploadedSBC(), priority=100)
# PlanLibrary (CO-12C): confirmed plan-level design, consulted below the primary SBC
# adapter. resolve(CoverageSource) still returns UserUploadedSBC (passthrough).
_registry.register_adapter(CoverageSource, PlanLibrary(), priority=50)
_registry.register_adapter(ClaimsSource, UserUploadedEOB(), priority=100)
# AccumulatorSource (CO-12B): the deterministic reconstruction is authoritative; the
# EOB-stated YTD is a corroborating reading for cross-validation (never adopted).
_registry.register_adapter(AccumulatorSource, ComputedFromUploadedEOBs(), priority=100)
_registry.register_adapter(AccumulatorSource, EOBStatedYTD(), priority=50)
# ClinicalEncounterSource (CO-12D): real shim over the Phase-2I encounter data. A
# OneUpHealthClinical adapter registers behind this same interface later (zero agent change).
_registry.register_adapter(ClinicalEncounterSource, UserUploadedVisitSummary(), priority=100)

# --- Coverage connection (1upHealth wrapper) — GATED OFF by default ------------
# Registered ONLY when enable_coverage_connection is on AND the wrapper URL/token
# are set (coverage_connection_ready). Priority 40 keeps these strictly BELOW the
# upload adapters (100) and the corroborators (50), so resolve()'s single-adapter
# passthrough still returns the upload path unchanged — the wrapper adapters are
# available for the CO-12B cross-validation step, not as a silent override. With
# the flag off (the shipped default) this block is a no-op and the source layer is
# byte-for-byte what it was before the wrapper landed.
if get_settings().coverage_connection_ready():
    from app.sources.adapters.oneup_wrapper_client import (
        OneUpWrapperAccumulator,
        OneUpWrapperClaims,
        OneUpWrapperCoverage,
    )

    _registry.register_adapter(CoverageSource, OneUpWrapperCoverage(), priority=40)
    _registry.register_adapter(ClaimsSource, OneUpWrapperClaims(), priority=40)
    _registry.register_adapter(AccumulatorSource, OneUpWrapperAccumulator(), priority=40)
    log.info("sources.coverage_connection_registered", priority=40)

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
