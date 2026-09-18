"""Human Review Phase 1 — queue policy (doc 39 §7-2d, 2026-09-18): the sample dial, the
always-enqueue triggers, re_review linkage on a re-run, and the health-strip math."""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CaseReview
from app.review import queue as rq


def _facts(**over) -> rq.EnqueueFacts:
    base = dict(
        terminal_status="audit_complete",
        incomplete_reason=None,
        confidence_band="high",
        first_case=False,
        system_error=False,
        canary_flag=False,
        material_disagreement=False,
        findings_count=1,
        net_finding_usd=120.0,
        documents_fingerprint="abc",
    )
    base.update(over)
    return rq.EnqueueFacts(**base)


_ALL_ON = SimpleNamespace(
    review_trigger_first_case=True,
    review_trigger_low_confidence=True,
    review_trigger_system_error=True,
    review_trigger_canary=True,
    review_trigger_material_disagreement=True,
)


# ── the pure policy ──────────────────────────────────────────────────────────────────────


def test_dial_100_samples_every_run():
    d = rq.decide(_facts(), sample_pct=100, settings=_ALL_ON, roll=0.999)
    assert d.enqueue and d.sampled and d.triggers == ()


def test_dial_0_skips_a_plain_completed_run():
    d = rq.decide(_facts(), sample_pct=0, settings=_ALL_ON, roll=0.0)
    assert not d.enqueue and not d.sampled and d.triggers == ()


def test_partial_dial_uses_the_roll():
    assert rq.decide(_facts(), sample_pct=25, settings=_ALL_ON, roll=0.10).sampled
    assert not rq.decide(_facts(), sample_pct=25, settings=_ALL_ON, roll=0.25).sampled
    assert not rq.decide(_facts(), sample_pct=25, settings=_ALL_ON, roll=0.90).sampled


@pytest.mark.parametrize(
    "field,trigger",
    [
        ("first_case", "first_case"),
        ("system_error", "system_error"),
        ("canary_flag", "canary"),
        ("material_disagreement", "material_disagreement"),
    ],
)
def test_always_enqueue_triggers_fire_regardless_of_dial(field, trigger):
    d = rq.decide(_facts(**{field: True}), sample_pct=0, settings=_ALL_ON, roll=0.0)
    assert d.enqueue and not d.sampled and d.triggers == (trigger,)


def test_low_confidence_band_is_a_trigger():
    d = rq.decide(_facts(confidence_band="low"), sample_pct=0, settings=_ALL_ON, roll=0.0)
    assert d.triggers == ("low_confidence",)
    for band in ("high", "medium", "unknown"):
        assert not rq.decide(_facts(confidence_band=band), sample_pct=0, settings=_ALL_ON, roll=0.0).enqueue


def test_triggers_are_config_not_code():
    off = SimpleNamespace(**{**vars(_ALL_ON), "review_trigger_canary": False})
    d = rq.decide(_facts(canary_flag=True), sample_pct=0, settings=off, roll=0.0)
    assert not d.enqueue and d.triggers == ()


def test_confidence_band_from_disclosure_tier():
    assert rq.confidence_band(None) == "unknown"
    assert rq.confidence_band(0) == "high" and rq.confidence_band(1) == "high"
    assert rq.confidence_band(2) == "medium"
    assert rq.confidence_band(3) == "low"


def test_documents_fingerprint_tracks_inventory_not_text():
    a = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf", "ocr_text": "x"}])
    b = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf", "ocr_text": "yyy"}])
    c = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf"}, {"document_type": "eob"}])
    assert a == b and a != c


# ── the DB path ──────────────────────────────────────────────────────────────────────────


async def _dev_admin_id() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _set_dial(pct: int) -> None:
    async with AsyncSessionLocal() as s:
        await rq.set_sample_pct(s, pct, admin_id=await _dev_admin_id())
        await s.commit()


async def _case(**fields) -> str:
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status=fields.pop("status", "audit_complete"), **fields)
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _get(review_id: str) -> CaseReview:
    async with AsyncSessionLocal() as s:
        return await s.get(CaseReview, uuid.UUID(review_id))


async def _decide(review_id: str, state: str = "approved") -> uuid.UUID:
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        row = await s.get(CaseReview, uuid.UUID(review_id))
        v = AdminVerdict(admin_user_id=uid, case_file_id=row.case_file_id, verdict="correct")
        s.add(v)
        await s.flush()
        row.state = state
        row.verdict_id = v.verdict_id
        row.reviewer_id = uid
        row.decided_at = datetime.datetime.now(datetime.timezone.utc)
        await s.commit()
        return v.verdict_id


@pytest.mark.asyncio
async def test_on_terminal_enqueues_then_rerun_after_decision_links_re_review():
    await _set_dial(100)
    try:
        cfid = await _case(documents=[{"document_type": "bill", "filename": "a.pdf"}])
        rid = await rq.on_terminal(cfid, "audit_complete", None)
        assert rid
        row = await _get(rid)
        assert row.state == "unreviewed" and row.run_seq == 1 and row.sampled
        assert row.terminal_status == "audit_complete" and row.prior_review_id is None

        vid = await _decide(rid, "approved")

        async with AsyncSessionLocal() as s:
            cf = await s.get(CaseFile, uuid.UUID(cfid))
            cf.documents = [*cf.documents, {"document_type": "eob", "filename": "b.pdf"}]
            await s.commit()
        rid2 = await rq.on_terminal(cfid, "audit_complete", None)
        assert rid2 and rid2 != rid
        row2 = await _get(rid2)
        assert row2.state == "re_review" and row2.run_seq == 2
        assert row2.prior_review_id == uuid.UUID(rid)
        assert "re_run" in row2.triggers and "documents_changed" in row2.triggers
        # the prior verdict is KEPT — never overwritten
        row1 = await _get(rid)
        assert row1.state == "approved" and row1.verdict_id == vid
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_rerun_after_document_change_is_forced_even_at_dial_0():
    await _set_dial(100)
    try:
        cfid = await _case(documents=[{"document_type": "bill", "filename": "a.pdf"}])
        rid = await rq.on_terminal(cfid, "audit_complete", None)
        await _decide(rid, "disapproved")
        await _set_dial(0)
        async with AsyncSessionLocal() as s:
            cf = await s.get(CaseFile, uuid.UUID(cfid))
            cf.documents = [{"document_type": "bill", "filename": "a-v2.pdf"}]
            await s.commit()
        rid2 = await rq.on_terminal(cfid, "audit_complete", None)
        assert rid2 is not None
        row2 = await _get(rid2)
        assert row2.state == "re_review" and not row2.sampled
        assert row2.prior_review_id == uuid.UUID(rid)
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_pending_row_is_restamped_not_duplicated():
    await _set_dial(100)
    try:
        cfid = await _case()
        rid = await rq.on_terminal(cfid, "audit_complete", None)
        rid_again = await rq.on_terminal(cfid, "audit_incomplete", "needs_documents")
        assert rid_again == rid
        row = await _get(rid)
        assert row.run_seq == 2 and row.state == "unreviewed"
        assert row.terminal_status == "audit_incomplete" and row.incomplete_reason == "needs_documents"
        async with AsyncSessionLocal() as s:
            n = len((await s.execute(select(CaseReview).where(CaseReview.case_file_id == uuid.UUID(cfid)))).scalars().all())
        assert n == 1
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_system_error_and_canary_enqueue_at_dial_0():
    await _set_dial(0)
    try:
        # Full cost-share coverage → disclosure tier 0 → no low_confidence trigger; nothing
        # else fires, so at dial 0 the policy skips it.
        plain = await _case(coverage={"deductible_amount": 2000, "oop_max_amount": 6000, "coinsurance_percent": 0.2})
        assert await rq.on_terminal(plain, "audit_complete", None) is None

        err = await _case(status="audit_incomplete", audit_incomplete_reason="system_error")
        rid = await rq.on_terminal(err, "audit_incomplete", "system_error")
        row = await _get(rid)
        assert row.system_error and "system_error" in row.triggers and not row.sampled

        tripped = await _case(
            research_log=[{"kind": "tripwire", "which": "grounding_drop", "codes": ["02417"], "category": "bundling"}]
        )
        rid = await rq.on_terminal(tripped, "audit_complete", None)
        row = await _get(rid)
        assert row.canary_flag and "canary" in row.triggers
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_non_terminal_status_never_enqueues():
    assert await rq.on_terminal(await _case(), "audit_running", None) is None


@pytest.mark.asyncio
async def test_health_approval_rate_excludes_cant_verify():
    # Decided far in the past so the window is isolated from live rows; asserted as a delta
    # so reruns against the shared local DB stay honest.
    t0 = datetime.datetime(2019, 3, 1, tzinfo=datetime.timezone.utc)
    uid = await _dev_admin_id()
    async with AsyncSessionLocal() as s:
        before = await rq.health(s, now=t0 + datetime.timedelta(days=1))
    async with AsyncSessionLocal() as s:
        cfid = uuid.UUID(await _case())
        for state in ("approved", "approved", "disapproved", "cant_verify", "cant_verify", "cant_verify"):
            s.add(
                CaseReview(
                    case_file_id=cfid, run_seq=1, state=state, reviewer_id=uid,
                    terminal_status="audit_complete", enqueued_at=t0, decided_at=t0,
                )
            )
        await s.commit()
    async with AsyncSessionLocal() as s:
        h = await rq.health(s, now=t0 + datetime.timedelta(days=1))
    assert h["approved_7d"] - before["approved_7d"] == 2
    assert h["disapproved_7d"] - before["disapproved_7d"] == 1
    # the three cant_verify rows moved neither side of the ratio
    assert h["approval_rate_7d"] == pytest.approx(h["approved_7d"] / (h["approved_7d"] + h["disapproved_7d"]), abs=1e-4)
    assert h["approval_rate_30d"] == pytest.approx(h["approved_30d"] / (h["approved_30d"] + h["disapproved_30d"]), abs=1e-4)
    assert "unreviewed" in h and "median_age_hours" in h and "in_review" in h


@pytest.mark.asyncio
async def test_health_rate_is_null_when_nothing_decided():
    t0 = datetime.datetime(2018, 6, 1, tzinfo=datetime.timezone.utc)
    async with AsyncSessionLocal() as s:
        h = await rq.health(s, now=t0)
    assert h["approval_rate_7d"] is None and h["approved_7d"] == 0
