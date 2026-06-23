"""CO-12A — data-interface seam + Provenance tests (DL-68, DL-69).

Locks:
  * single-adapter passthrough resolution;
  * the two "now" adapters return data + a well-formed Provenance;
  * the AccumulatorSource as_of contract (DL-69) — both the placeholder echoing it
    and the type rejecting a null as_of;
  * the ZERO-AGENT-CHANGE regression — upload_extract_{coverage,eob} still return
    their original core keys/types, with `provenance` purely additive.

use_real_ocr defaults false, so extraction runs the keyword stub — deterministic
and credential-free.
"""

from __future__ import annotations

import base64
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.provenance import Provenance
from app.sources import benefits_context, get_registry, resolve
from app.sources.base import (
    AccumulatorResult,
    AccumulatorSource,
    ClaimsSource,
    ClinicalEncounterSource,
    CoverageSource,
)
from app.tools import call_tool

_DOC = base64.b64encode(
    b"PLAN: Acme PPO PAYER: UnitedHealthcare MEMBER ID: 12345 "
    b"BILLED $1200 ALLOWED $830 PATIENT RESPONSIBILITY $370"
).decode()
_ARGS = {"content_base64": _DOC, "filename": "doc.txt"}


# --- registry ---------------------------------------------------------------
def test_registry_single_adapter_passthrough():
    reg = get_registry()
    cov = reg.resolve(CoverageSource)
    assert cov is resolve(CoverageSource)  # module-level resolve hits the default registry
    assert reg.adapters_for(CoverageSource) == [cov]  # exactly one adapter today
    assert type(cov).__name__ == "UserUploadedSBC"
    assert type(reg.resolve(ClaimsSource)).__name__ == "UserUploadedEOB"


def test_registry_unknown_interface_raises():
    class Nope: ...

    with pytest.raises(LookupError):
        get_registry().resolve(Nope)


# --- "now" adapters ---------------------------------------------------------
@pytest.mark.asyncio
async def test_coverage_adapter_returns_data_plus_provenance():
    result = await resolve(CoverageSource).get_coverage("", _ARGS)
    assert {"coverage", "coverage_terms_confidence", "raw_ocr"} <= set(result.data)
    p = result.provenance
    assert isinstance(p, Provenance)
    assert p.adapter == "UserUploadedSBC"
    assert p.source_kind == "user_upload"
    assert 0.0 <= p.confidence <= 1.0
    assert p.as_of is None


@pytest.mark.asyncio
async def test_claims_adapter_returns_data_plus_provenance():
    result = await resolve(ClaimsSource).get_claims("", _ARGS)
    assert {"eob", "raw_ocr"} <= set(result.data)
    p = result.provenance
    assert p.adapter == "UserUploadedEOB"
    assert p.source_kind == "user_upload"
    assert 0.0 <= p.confidence <= 1.0


# --- DL-69 as_of contract ---------------------------------------------------
@pytest.mark.asyncio
async def test_accumulator_empty_case_zero_confidence():
    # CO-12B: the real engine (ComputedFromUploadedEOBs) now backs AccumulatorSource.
    # An unknown/invalid case -> empty reconstruction -> 0.0 confidence, but still a
    # valid result with a non-null as_of (DL-69).
    res = await resolve(AccumulatorSource).get_accumulator("cf", date(2026, 6, 1))
    assert res.provenance.as_of is not None
    assert res.provenance.confidence == 0.0
    assert res.provenance.source_kind == "computed"


def test_accumulator_result_rejects_null_as_of():
    # The DL-69 contract is baked into the type: no as_of -> invalid.
    with pytest.raises(ValidationError):
        AccumulatorResult(
            data={},
            provenance=Provenance(adapter="x", source_kind="computed", as_of=None, confidence=0.0),
        )


@pytest.mark.asyncio
async def test_encounter_placeholder_present():
    res = await resolve(ClinicalEncounterSource).get_encounter("cf")
    assert res.provenance.adapter == "PlaceholderClinicalEncounter"
    assert res.provenance.confidence == 0.0


# --- BenefitsContext facade -------------------------------------------------
@pytest.mark.asyncio
async def test_benefits_context_pairs_coverage_and_accumulator():
    cov = await benefits_context.get_coverage("", _ARGS)
    assert cov.provenance.adapter == "UserUploadedSBC"
    acc = await benefits_context.get_accumulator("cf", date(2026, 6, 1))
    assert acc.provenance.as_of is not None


# --- ZERO-AGENT-CHANGE regression guard -------------------------------------
@pytest.mark.asyncio
async def test_upload_extract_coverage_tool_core_keys_unchanged():
    out = await call_tool("upload_extract_coverage", _ARGS)
    # Original core keys + types, identical:
    assert isinstance(out["coverage"], dict)
    assert isinstance(out["coverage_terms_confidence"], dict)
    assert "overall" in out["coverage_terms_confidence"]
    assert isinstance(out["raw_ocr"], dict)
    assert set(out["coverage"]) == {
        "plan_name",
        "payer_name",
        "member_id",
        "deductible_amount",
        "deductible_met",
        "coinsurance_percent",
        "oop_max_amount",
        "oop_max_met",
        "network_tier",
    }
    # Additive only:
    assert isinstance(out["provenance"], dict)
    assert out["provenance"]["adapter"] == "UserUploadedSBC"
    assert out["provenance"]["source_kind"] == "user_upload"
    assert set(out["provenance"]) == {
        "adapter",
        "source_kind",
        "as_of",
        "confidence",
        "assumptions",
    }


@pytest.mark.asyncio
async def test_upload_extract_eob_tool_core_keys_unchanged():
    out = await call_tool("upload_extract_eob", _ARGS)
    assert isinstance(out["eob"], dict)
    # CO-12B added accumulator fields to `eob` additively; the original keys remain.
    assert {
        "claim_id",
        "billed_amount",
        "allowed_amount",
        "patient_responsibility",
        "remark_codes",
    } <= set(out["eob"])
    assert isinstance(out["raw_ocr"], dict)
    assert isinstance(out["provenance"], dict)
    assert out["provenance"]["adapter"] == "UserUploadedEOB"
