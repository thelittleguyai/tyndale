"""Gate logic for the 50-state + DC surprise-billing seed (DL-81), exercised against an
in-memory Qdrant. The retrieval smoke needs live embeddings, so these tests run the gate
in --no-retrieval mode and prove the structural half: jurisdiction presence counting,
schema validation, the x6 + non-null-ground-ambulance requirements, and the exit codes
(strict fail vs --allow-partial informational)."""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout

import pytest
import pytest_asyncio
from qdrant_client import models

from app.config import get_settings
from app.knowledge.client import ensure_collection, get_client
from scripts.check_state_seed import STATES, run


def _args(**over) -> argparse.Namespace:
    base = dict(
        no_retrieval=True,
        strict=False,
        allow_partial=False,
        effective_date="2026-07-04",
        top_k=30,
        top_n=8,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _rec(code: str, ground: bool | None = False, **over) -> dict:
    rec = {
        "chunk_id": f"{code.lower()}_balance_billing",
        "jurisdiction": f"state_{code}",
        "statute": f"{code} Ins. Code",
        "section": "1.1",
        "effective_date_start": "2022-01-01",
        "effective_date_end": None,
        "document_type": "statute",
        "chunk_text": f"{code} balance-billing protection (test fixture).",
        "last_verified_date": "2026-07-03",
        "x6_classification": "CATEGORICAL",
        "checkable_facts": [],
        "defeaters": [],
        "scope": {"plan_types_bound": ["state_regulated_commercial"], "ground_ambulance_covered": ground},
        "as_of": "2026-07-03",
    }
    rec.update(over)
    return rec


async def _seed(records: list[dict]) -> None:
    await ensure_collection("laws_regulations", 1024, hybrid_enabled=False)
    await get_client().upsert(
        collection_name="laws_regulations",
        points=[
            models.PointStruct(id=i + 1, vector=[0.1] * 1024, payload=rec)
            for i, rec in enumerate(records)
        ],
    )


async def _run_capture(args: argparse.Namespace) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = await run(args)
    return code, buf.getvalue()


@pytest_asyncio.fixture
async def memory_qdrant(monkeypatch):
    import app.knowledge.client as kc

    monkeypatch.setattr(get_settings(), "qdrant_url", ":memory:")
    monkeypatch.setattr(get_settings(), "voyage_api_key", None)
    kc._client = None
    yield
    kc._client = None


@pytest.mark.asyncio
async def test_incomplete_seed_reports_gate_not_met(memory_qdrant):
    # Only 5 of 51 jurisdictions present → gate not met; --allow-partial keeps exit 0.
    await _seed([_rec(c) for c in ("CA", "NY", "TX", "FL", "WY")])
    code, out = await _run_capture(_args(allow_partial=True))
    assert "5/51" in out
    assert "GATE: NOT MET" in out
    assert code == 0  # informational mode
    # Without --allow-partial the same incomplete seed is a hard failure.
    code2, _ = await _run_capture(_args(allow_partial=False))
    assert code2 == 1


@pytest.mark.asyncio
async def test_complete_seed_passes(memory_qdrant):
    await _seed([_rec(c) for c in STATES])
    code, out = await _run_capture(_args())
    assert "51/51" in out
    assert "GATE: PASS" in out
    assert code == 0


@pytest.mark.asyncio
async def test_state_law_binding_fehb_pshb_fails_gate(memory_qdrant):
    # HARD RULE (Brock 2026-07-06): FEHBA preempts state insurance law, so a STATE-jurisdiction
    # entry binding fehb_pshb is a wrong-answer error — an otherwise complete seed must NOT pass.
    recs = [_rec(c) for c in STATES]
    recs[0]["scope"]["plan_types_bound"] = ["state_regulated_commercial", "fehb_pshb"]
    await _seed(recs)
    code, out = await _run_capture(_args())
    assert "state law binding fehb_pshb  : 1" in out
    assert "GATE: PASS" not in out
    assert code == 1


@pytest.mark.asyncio
async def test_null_ground_ambulance_fails_gate(memory_qdrant):
    # All 51 present + schema-valid (null ground ambulance IS schema-legal), but the gate
    # forbids a null ground-ambulance answer for the seed.
    records = [_rec(c) for c in STATES]
    records[0]["scope"]["ground_ambulance_covered"] = None
    await _seed(records)
    code, out = await _run_capture(_args())
    assert "null ground-ambulance answer : 1" in out
    assert "GATE: NOT MET" in out
    assert code == 1


@pytest.mark.asyncio
async def test_strict_requires_retrieval_to_run(memory_qdrant):
    # Complete + valid, but --strict + --no-retrieval means the retrieval smoke never ran.
    await _seed([_rec(c) for c in STATES])
    code, out = await _run_capture(_args(strict=True))
    assert "GATE: FAIL" in out
    assert code == 1
