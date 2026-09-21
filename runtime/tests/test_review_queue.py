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
    for band in ("high", "medium"):
        assert not rq.decide(_facts(confidence_band=band), sample_pct=0, settings=_ALL_ON, roll=0.0).enqueue


def test_an_unprojectable_run_counts_as_low_confidence_for_the_trigger():
    """Deep review: band 'unknown' means the result could not even be projected — the run that
    most needs eyes. At a sampled dial it used to slip through as if it were fine."""
    d = rq.decide(_facts(confidence_band="unknown"), sample_pct=0, settings=_ALL_ON, roll=0.99)
    assert d.enqueue and d.triggers == ("low_confidence",)
    off = SimpleNamespace(**{**vars(_ALL_ON), "review_trigger_low_confidence": False})
    assert not rq.decide(_facts(confidence_band="unknown"), sample_pct=0, settings=off, roll=0.99).enqueue


def test_triggers_are_config_not_code():
    off = SimpleNamespace(**{**vars(_ALL_ON), "review_trigger_canary": False})
    d = rq.decide(_facts(canary_flag=True), sample_pct=0, settings=off, roll=0.0)
    assert not d.enqueue and d.triggers == ()


def test_confidence_band_from_disclosure_tier():
    assert rq.confidence_band(None) == "unknown"
    assert rq.confidence_band(0) == "high" and rq.confidence_band(1) == "high"
    assert rq.confidence_band(2) == "medium"
    assert rq.confidence_band(3) == "low"


def test_documents_fingerprint_is_document_identity_not_extraction_state():
    """Deep review: hashing every non-text field meant a mutable extraction field changing
    between runs read as 'documents changed' and forced a spurious re_review."""
    doc = {"document_id": "d-1", "uri": "https://acct/uploads/abc_bill.pdf", "byte_count": 1234,
           "filename": "bill.pdf", "document_type": "bill", "extraction_status": "extracted",
           "ocr_text_chars": 900, "page_count": 2, "provider_name": "UMC", "ocr_text": "x"}
    base = rq.documents_fingerprint([doc])
    mutated = {**doc, "extraction_status": "error", "ocr_text_chars": 0, "page_count": 3,
               "provider_name": "Univ. Medical Center", "ocr_text": "yyy", "ocr_text_preview": "y",
               "document_type": "statement"}
    assert rq.documents_fingerprint([mutated]) == base  # same document, different extraction
    assert rq.documents_fingerprint([{**doc, "document_id": "d-2"}]) != base  # a different document
    assert rq.documents_fingerprint([{**doc, "uri": "https://acct/uploads/zzz_bill.pdf"}]) != base
    assert rq.documents_fingerprint([doc, {"document_id": "d-9", "uri": "u9"}]) != base  # one more
    # order never matters; an EOB is part of the inventory too
    other = {"document_id": "d-9", "uri": "u9"}
    assert rq.documents_fingerprint([doc, other]) == rq.documents_fingerprint([other, doc])
    assert rq.documents_fingerprint([doc], [{"document_id": "e-1", "uri": "ue"}]) != base
    # rows older than document_id fall back to filename + type, so they still differentiate
    a = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf", "ocr_text": "x"}])
    b = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf", "ocr_text": "yyy"}])
    c = rq.documents_fingerprint([{"document_type": "bill", "filename": "a.pdf"}, {"document_type": "eob"}])
    assert a == b and a != c


def test_sampling_draw_is_a_pure_function_of_the_case():
    """Deep review: a random draw re-rolled on every re-run, so at dial 25 'not sampled' only
    meant 'not yet'. The draw is now derived from the case id."""
    ids = [uuid.uuid4() for _ in range(400)]
    rolls = [rq.stable_roll(i) for i in ids]
    assert all(0.0 <= r < 1.0 for r in rolls)
    assert [rq.stable_roll(i) for i in ids] == rolls  # same case, same draw — every time
    assert rq.stable_roll(str(ids[0])) == rolls[0]  # str or UUID
    share = sum(1 for r in rolls if r * 100 < 25) / len(rolls)
    assert 0.15 < share < 0.35  # ~25% at dial 25 — a sanity band, not a statistics test
    assert len({round(r, 2) for r in rolls}) > 50  # it actually spreads


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
        states = ("approved", "approved", "disapproved", "cant_verify", "cant_verify", "cant_verify")
        for seq, state in enumerate(states, start=1):  # one row per RUN (uq_case_reviews_case_run)
            s.add(
                CaseReview(
                    case_file_id=cfid, run_seq=seq, state=state, reviewer_id=uid,
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



# ══ deep review (2026-09-18): correctness under re-runs and concurrency ══════════════════════

_FULL_COVERAGE = {"deductible_amount": 2000, "oop_max_amount": 6000, "coinsurance_percent": 0.2}


@pytest.mark.asyncio
async def test_a_case_skipped_by_the_dial_stays_skipped_on_every_rerun():
    await _set_dial(50)
    try:
        cfid = None
        for _ in range(40):  # find a fully-grounded case whose stable draw misses a 50% dial
            candidate = await _case(coverage=_FULL_COVERAGE)
            if rq.stable_roll(candidate) * 100 >= 50:
                cfid = candidate
                break
        assert cfid is not None
        # not the user's first case, tier 0, no tripwire -> nothing but the dial decides
        for _ in range(5):
            assert await rq.on_terminal(cfid, "audit_complete", None) is None
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_first_case_is_the_users_earliest_case_not_a_case_count():
    from app.db.models.users import User

    async with AsyncSessionLocal() as s:
        u = User(email=f"fc{uuid.uuid4().hex[:10]}@example.com", user_type="user")
        s.add(u)
        await s.flush()
        first = CaseFile(user_id=u.user_id, status="audit_complete",
                         created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
        junk = CaseFile(user_id=u.user_id, status="open",
                        created_at=datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc),
                        soft_deleted_at=datetime.datetime(2025, 12, 2, tzinfo=datetime.timezone.utc))
        second = CaseFile(user_id=u.user_id, status="audit_complete",
                          created_at=datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc))
        s.add_all([first, junk, second])
        await s.commit()
        first_id, second_id = first.case_file_id, second.case_file_id
    async with AsyncSessionLocal() as s:
        f1 = await rq.gather_facts(s, await s.get(CaseFile, first_id), "audit_complete", None)
        f2 = await rq.gather_facts(s, await s.get(CaseFile, second_id), "audit_complete", None)
    # `count <= 1` said False for BOTH once the second case existed; a removed junk upload
    # that happens to be older must not steal "first" either.
    assert f1.first_case is True and f2.first_case is False


@pytest.mark.asyncio
async def test_an_unprojectable_case_is_enqueued_even_at_dial_0(monkeypatch):
    from app.agents import orchestrator

    async def boom(*a, **k):
        raise RuntimeError("cannot project this case")

    monkeypatch.setattr(orchestrator, "_assemble_result", boom)
    await _set_dial(0)
    try:
        rid = await rq.on_terminal(await _case(coverage=_FULL_COVERAGE), "audit_complete", None)
        row = await _get(rid)
        assert row.confidence_band == "unknown" and row.triggers == ["low_confidence"] and not row.sampled
    finally:
        await _set_dial(100)


@pytest.mark.asyncio
async def test_re_review_survives_a_rerun_while_the_row_is_still_pending():
    await _set_dial(100)
    cfid = await _case(documents=[{"document_id": "d-1", "uri": "u1"}])
    rid = await rq.on_terminal(cfid, "audit_complete", None)
    await _decide(rid, "disapproved")
    async with AsyncSessionLocal() as s:
        cf = await s.get(CaseFile, uuid.UUID(cfid))
        cf.documents = [*cf.documents, {"document_id": "d-2", "uri": "u2"}]
        await s.commit()
    rid2 = await rq.on_terminal(cfid, "audit_complete", None)
    assert (await _get(rid2)).state == "re_review"
    # …and the case runs AGAIN before anyone looks: same pending row, still a re_review
    rid3 = await rq.on_terminal(cfid, "audit_incomplete", "needs_documents")
    row = await _get(rid3)
    assert rid3 == rid2 and row.state == "re_review" and row.run_seq == 3
    assert row.prior_review_id == uuid.UUID(rid) and row.terminal_status == "audit_incomplete"


@pytest.mark.asyncio
async def test_one_row_per_case_run_under_concurrency_and_by_constraint():
    import asyncio

    from sqlalchemy.exc import IntegrityError

    await _set_dial(100)
    cfid = await _case()
    ids = await asyncio.gather(*[rq.on_terminal(cfid, "audit_complete", None) for _ in range(4)])
    assert len(set(ids)) == 1 and ids[0]  # serialized on the case row: one row, re-stamped
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(CaseReview).where(CaseReview.case_file_id == uuid.UUID(cfid)))).scalars().all()
    assert len(rows) == 1 and rows[0].run_seq == 4

    with pytest.raises(IntegrityError):  # uq_case_reviews_case_run is the backstop
        async with AsyncSessionLocal() as s:
            s.add(CaseReview(case_file_id=uuid.UUID(cfid), run_seq=4, state="unreviewed",
                             terminal_status="audit_complete"))
            await s.commit()
