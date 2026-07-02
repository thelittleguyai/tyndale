"""CO-12B — deterministic accumulator engine + three-way cross-validation (DL-72).

Pure-function tests (no DB, no LLM) for the reconstruction math, the EOB-stated
reading, and the cross-validation; an injected-writer test that asserts the
discrepancy finding without a live DB; and an additive-regression test on EOB
extraction.
"""

from __future__ import annotations

import base64
from datetime import date, datetime

import pytest

from app.schemas.provenance import Provenance
from app.sources.adapters.computed_from_uploaded_eobs import (
    ComputedFromUploadedEOBs,
    completeness_signal,
    compute_accumulator,
)
from app.sources.adapters.eob_stated_ytd import read_eob_stated_ytd
from app.sources.base import AccumulatorResult, AccumulatorSource
from app.sources.benefits_context import BenefitsContext, cross_validate
from app.sources.extraction import extract_eob_payload
from app.sources.registry import SourceRegistry

AS_OF = date(2026, 6, 1)


def _eob(**kw) -> dict:
    base = {
        "adjudication_date": None,
        "date_of_service": None,
        "amount_applied_to_deductible": None,
        "amount_applied_to_oop": None,
        "deductible_ytd_stated": None,
        "oop_ytd_stated": None,
        "network_status": None,
    }
    base.update(kw)
    return base


class _StubAccumulator:
    """A minimal AccumulatorSource returning crafted data (no DB)."""

    def __init__(self, name: str, data: dict) -> None:
        self.adapter_name = name
        self._data = data

    async def get_accumulator(self, case_file_id, as_of, args=None) -> AccumulatorResult:
        return AccumulatorResult(
            data=self._data,
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="computed" if "Computed" in self.adapter_name else "user_upload",
                as_of=datetime(as_of.year, as_of.month, as_of.day),
                confidence=0.5,
                assumptions=[],
            ),
        )


# --- pure engine ------------------------------------------------------------
def test_sums_and_single_bucket_degradation():
    eobs = [
        _eob(
            adjudication_date="2026-02-01",
            amount_applied_to_deductible=200.0,
            amount_applied_to_oop=200.0,
        ),
        _eob(
            adjudication_date="2026-03-01",
            amount_applied_to_deductible=150.0,
            amount_applied_to_oop=175.0,
        ),
    ]
    comp = compute_accumulator(
        eobs, {"deductible_amount": 1000.0, "oop_max_amount": 5000.0}, AS_OF, True
    )
    assert comp.data["deductible_applied"] == 350.0
    assert comp.data["oop_applied"] == 375.0
    assert comp.data["deductible_remaining"] == 650.0
    assert comp.data["oop_remaining"] == 4625.0
    assert comp.data["eobs_counted"] == 2
    assert "individual_in_network" in comp.data["buckets"]
    assert any("single bucket" in a for a in comp.assumptions)


def test_dos_fallback_flagged_and_plan_year_filter():
    eobs = [
        _eob(date_of_service="2026-01-15", amount_applied_to_deductible=100.0),  # DOS fallback
        _eob(
            adjudication_date="2025-12-01", amount_applied_to_deductible=999.0
        ),  # prior year -> excluded
    ]
    comp = compute_accumulator(eobs, {}, AS_OF, True)
    assert comp.data["deductible_applied"] == 100.0
    assert comp.data["eobs_counted"] == 1
    assert any("date_of_service used as fallback" in a for a in comp.assumptions)


def test_undated_included_and_flagged():
    comp = compute_accumulator([_eob(amount_applied_to_deductible=50.0)], {}, AS_OF, True)
    assert comp.data["deductible_applied"] == 50.0
    assert comp.data["eobs_counted"] == 1
    assert any("undated" in a for a in comp.assumptions)


def test_completeness_gate_lowers_confidence_and_records_assumption():
    eobs = [_eob(adjudication_date="2026-02-01", amount_applied_to_deductible=200.0)]
    confirmed = compute_accumulator(eobs, {}, AS_OF, True)
    unconfirmed = compute_accumulator(eobs, {}, AS_OF, None)
    assert unconfirmed.confidence < confirmed.confidence
    assert any("history may be incomplete" in a for a in unconfirmed.assumptions)
    assert not any("history may be incomplete" in a for a in confirmed.assumptions)


def test_empty_set_zero_confidence():
    comp = compute_accumulator([], None, AS_OF, True)
    assert comp.confidence == 0.0
    assert comp.data["deductible_applied"] == 0.0
    assert comp.data["eobs_counted"] == 0


def test_completeness_signal_sources():
    assert completeness_signal({"all_eobs_uploaded": True}, None) is True
    assert completeness_signal({"all_eobs_uploaded": False}, None) is False
    assert completeness_signal(None, {"_all_eobs_uploaded": True}) is True
    assert completeness_signal(None, None) is None


@pytest.mark.asyncio
async def test_adapter_result_has_non_null_as_of_dl69():
    # Invalid case id -> graceful empty load (no DB) -> still a valid result with as_of.
    res = await ComputedFromUploadedEOBs().get_accumulator("not-a-uuid", AS_OF)
    assert isinstance(res, AccumulatorResult)
    assert res.provenance.as_of is not None
    assert res.provenance.source_kind == "computed"


# --- EOB-stated YTD ---------------------------------------------------------
def test_eob_stated_latest_wins():
    eobs = [
        _eob(adjudication_date="2026-02-01", deductible_ytd_stated=300.0, oop_ytd_stated=300.0),
        _eob(adjudication_date="2026-05-01", deductible_ytd_stated=800.0, oop_ytd_stated=900.0),
    ]
    stated = read_eob_stated_ytd(eobs, AS_OF)
    assert stated["deductible_applied"] == 800.0
    assert stated["oop_applied"] == 900.0


# --- three-way cross-validation ---------------------------------------------
def test_cross_val_agreement_no_finding():
    cv = cross_validate(
        {"deductible_applied": 500.0, "oop_applied": 800.0},
        {"deductible_applied": 500.0, "oop_applied": 800.0},
        {"deductible_met": 500.0, "oop_max_met": 800.0},
        AS_OF,
    )
    assert cv.agreement is True
    assert cv.finding_spec is None


def test_cross_val_within_tolerance_no_finding():
    cv = cross_validate(
        {"deductible_applied": 500.00, "oop_applied": 800.0},
        {"deductible_applied": 500.50, "oop_applied": 800.0},  # 50c < $1 -> immaterial
        {},
        AS_OF,
    )
    assert cv.agreement is True
    assert cv.finding_spec is None


def test_cross_val_absolute_floor_catches_large_dollar_small_percent():
    # $30 gap on a ~$5,000 deductible = 0.6% — under the 5% test, so the old
    # rule would MISS it. Brock's $25 absolute floor (DL-72, 2026-06-26) catches it.
    cv = cross_validate(
        {"deductible_applied": 5000.0, "oop_applied": 800.0},  # computed
        {"deductible_applied": 5030.0, "oop_applied": 800.0},  # eob-stated: +$30 (0.6%)
        {},
        AS_OF,
    )
    assert cv.agreement is False
    assert cv.finding_spec is not None
    assert cv.finding_spec["category"] == "accumulator_discrepancy"


def test_cross_val_under_absolute_floor_and_under_percent_immaterial():
    # $20 gap on ~$5,000 = 0.4%: under BOTH the $25 floor and the 5% test → immaterial.
    cv = cross_validate(
        {"deductible_applied": 5000.0, "oop_applied": 800.0},
        {"deductible_applied": 5020.0, "oop_applied": 800.0},
        {},
        AS_OF,
    )
    assert cv.agreement is True
    assert cv.finding_spec is None


def test_cross_val_material_disagreement_one_finding():
    cv = cross_validate(
        {"deductible_applied": 500.0, "oop_applied": 800.0},  # computed (authoritative)
        {"deductible_applied": 1500.0, "oop_applied": 800.0},  # eob-stated disagrees
        {"deductible_met": 500.0, "oop_max_met": 800.0},  # coverage-stated
        AS_OF,
    )
    assert cv.agreement is False
    spec = cv.finding_spec
    assert spec is not None
    assert spec["category"] == "accumulator_discrepancy"
    assert spec["finding_type"] == "payer_side"
    assert spec["voice_tier"] == "A"
    assert spec["subagent_source"] == "math_person"
    assert set(spec["facts"]["readings"]) == {"computed", "eob_stated", "coverage_stated"}
    assert spec["facts"]["as_of"] == AS_OF.isoformat()


@pytest.mark.asyncio
async def test_get_accumulator_emits_finding_via_injected_writer(monkeypatch):
    # Stub adapters + monkeypatched coverage read -> no live DB; assert the writer fires.
    reg = SourceRegistry()
    reg.register_adapter(
        AccumulatorSource,
        _StubAccumulator(
            "ComputedFromUploadedEOBs", {"deductible_applied": 500.0, "oop_applied": 0.0}
        ),
        priority=100,
    )
    reg.register_adapter(
        AccumulatorSource,
        _StubAccumulator("EOBStatedYTD", {"deductible_applied": 1500.0, "oop_applied": 0.0}),
        priority=50,
    )

    async def _fake_load(_case_file_id):
        return [], {"deductible_met": 500.0, "oop_max_met": 0.0}

    # NB: the package attr `app.sources.benefits_context` is the singleton INSTANCE,
    # which shadows the submodule by name (even for `import ... as`) — reach the real
    # module via sys.modules and patch it there.
    import sys

    bc_module = sys.modules["app.sources.benefits_context"]
    monkeypatch.setattr(bc_module, "load_case_eobs_coverage", _fake_load)

    collected: list[dict] = []

    async def _writer(_cf, spec):
        collected.append(spec)

    res = await BenefitsContext(reg).get_accumulator(
        "00000000-0000-0000-0000-000000000001", AS_OF, finding_writer=_writer
    )
    assert res.data["deductible_applied"] == 500.0  # computed is authoritative
    assert (
        len(collected) == 1
    )  # exactly one discrepancy finding (eob 1500 vs computed/coverage 500)
    assert collected[0]["category"] == "accumulator_discrepancy"


# --- regression: extract_eob_payload additive only --------------------------
@pytest.mark.asyncio
async def test_extract_eob_keeps_core_keys_additive():
    doc = base64.b64encode(
        b"CLAIM CL-1 BILLED $1200 ALLOWED $830 PATIENT RESPONSIBILITY $370"
    ).decode()
    out = await extract_eob_payload({"content_base64": doc, "filename": "eob.txt"})
    eob = out["eob"]
    assert {
        "claim_id",
        "billed_amount",
        "allowed_amount",
        "patient_responsibility",
        "remark_codes",
    } <= set(eob)
    assert isinstance(eob["remark_codes"], list)
    assert {
        "adjudication_date",
        "date_of_service",
        "amount_applied_to_deductible",
        "amount_applied_to_oop",
        "network_status",
        "deductible_ytd_stated",
        "oop_ytd_stated",
    } <= set(eob)
    assert "raw_ocr" in out
