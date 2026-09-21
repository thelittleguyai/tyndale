"""Deep review C5 (2026-09-18): synthetic e2e identities never enter the human-review queue,
and a run's teardown removes everything for THAT identity and nothing else."""

from __future__ import annotations

import datetime
import pathlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CaseReview
from app.db.models.conversations import Conversation
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.db.models.messages import Message
from app.db.models.users import User
from app.review import queue as rq
from app.synthetic_teardown import COVERED_FKS, DELETED_TABLES, NotSynthetic, teardown_synthetic_user


def _synth_email() -> str:
    return f"e2e-runner+{uuid.uuid4().hex[:12]}@e2e.tyndale.test"


async def _user(email: str) -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        u = User(email=email, user_type="user", first_name="Jordan", last_name="Testpatient")
        s.add(u)
        await s.commit()
        return u.user_id


async def _populated_case(user_id: uuid.UUID, admin_id: uuid.UUID) -> tuple[uuid.UUID, pathlib.Path]:
    """One case with a row in every table the teardown covers, and a real stored file."""
    uploads = pathlib.Path(get_settings().local_uploads_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    stored = uploads / f"{uuid.uuid4()}_bill.pdf"
    stored.write_bytes(b"%PDF-1.4 synthetic")
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=user_id,
            status="audit_complete",
            documents=[{"document_id": str(uuid.uuid4()), "document_type": "bill", "uri": str(stored)}],
        )
        s.add(cf)
        await s.flush()
        cid = cf.case_file_id
        s.add(Finding(case_file_id=cid, finding_type="payer_side", category="bundling",
                      subagent_source="bill_detective", voice_tier="A", facts={"gap": 1.0}, status="open"))
        s.add(Deadline(case_file_id=cid, deadline_date=datetime.date(2027, 1, 1),
                       deadline_type="erisa_internal_appeal", description="appeal window"))
        conv = Conversation(user_id=user_id, case_id=cid)
        s.add(conv)
        await s.flush()
        first = Message(conversation_id=conv.conversation_id, sequence_number=1, role="assistant",
                        content="result", status="complete")
        s.add(first)
        await s.flush()
        s.add(Message(conversation_id=conv.conversation_id, sequence_number=2, role="assistant",
                      content="correction", status="complete", corrects_message_id=first.message_id))
        verdict = AdminVerdict(admin_user_id=admin_id, case_file_id=cid, verdict="correct")
        s.add(verdict)
        await s.flush()
        s.add(CaseReview(case_file_id=cid, run_seq=1, state="approved", terminal_status="audit_complete",
                         verdict_id=verdict.verdict_id, reviewer_id=admin_id))
        s.add(FeedbackEvent(case_file_id=cid, user_id=user_id, feedback_type="thumbs_up", payload={}))
        s.add(AnalyticsEvent(event_name="upload_started", user_id=user_id, case_file_id=cid,
                             properties={"file_count": 1}))
        s.add(AuditEvent(event_type="system_action", actor="test", case_file_id=cid, user_id=user_id,
                         payload_encrypted=b"{}", payload_hash=b"\\x00" * 32, key_version=0, outcome="success"))
        await s.commit()
        return cid, stored


async def _admin_id() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _footprint(user_id: uuid.UUID, case_ids: list[uuid.UUID]) -> dict[str, int]:
    """Row counts per covered table for one identity."""
    ids = [str(c) for c in case_ids]
    q = {
        "users": ("SELECT count(*) FROM users WHERE user_id = :u", {"u": user_id}),
        "case_files": ("SELECT count(*) FROM case_files WHERE user_id = :u", {"u": user_id}),
        "findings": ("SELECT count(*) FROM findings WHERE case_file_id = ANY(CAST(:ids AS uuid[]))", {"ids": ids}),
        "deadlines": ("SELECT count(*) FROM deadlines WHERE case_file_id = ANY(CAST(:ids AS uuid[]))", {"ids": ids}),
        "conversations": ("SELECT count(*) FROM conversations WHERE user_id = :u", {"u": user_id}),
        "messages": ("SELECT count(*) FROM messages m JOIN conversations c USING (conversation_id) WHERE c.user_id = :u", {"u": user_id}),
        "case_reviews": ("SELECT count(*) FROM case_reviews WHERE case_file_id = ANY(CAST(:ids AS uuid[]))", {"ids": ids}),
        "admin_verdicts": ("SELECT count(*) FROM admin_verdicts WHERE case_file_id = ANY(CAST(:ids AS uuid[]))", {"ids": ids}),
        "feedback_events": ("SELECT count(*) FROM feedback_events WHERE user_id = :u", {"u": user_id}),
        "analytics_events": ("SELECT count(*) FROM analytics_events WHERE user_id = :u", {"u": user_id}),
        "audit_events": ("SELECT count(*) FROM audit_events WHERE case_file_id = ANY(CAST(:ids AS uuid[]))", {"ids": ids}),
    }
    out = {}
    async with AsyncSessionLocal() as s:
        for k, (sql, params) in q.items():
            out[k] = (await s.execute(text(sql), params)).scalar_one()
    return out


# ── the queue refuses synthetic identities ───────────────────────────────────────────────


def test_policy_refuses_a_synthetic_identity_whatever_the_dial_or_triggers():
    facts = rq.EnqueueFacts(
        terminal_status="audit_incomplete", incomplete_reason="system_error", confidence_band="low",
        first_case=True, system_error=True, canary_flag=True, material_disagreement=True,
        findings_count=3, net_finding_usd=900.0, documents_fingerprint="x", synthetic=True,
    )
    d = rq.decide(facts, sample_pct=100, roll=0.0)
    assert (d.enqueue, d.sampled, d.triggers, d.skipped) == (False, False, (), "synthetic")


@pytest.mark.asyncio
async def test_a_synthetic_users_runs_are_never_enqueued_and_the_skip_is_counted():
    admin = await _admin_id()
    async with AsyncSessionLocal() as s:
        await rq.set_sample_pct(s, 100, admin_id=admin)
        await s.commit()
    uid = await _user(_synth_email())
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status="audit_complete",
                      research_log=[{"kind": "tripwire", "which": "grounding_drop", "codes": ["02417"]}])
        s.add(cf)
        await s.commit()
        cid = cf.case_file_id

    assert await rq.on_terminal(str(cid), "audit_complete", None) is None  # dial 100 + canary
    assert await rq.on_terminal(str(cid), "audit_incomplete", "system_error") is None  # trigger

    # even the FORCED path: a decided row whose documents then changed
    async with AsyncSessionLocal() as s:
        s.add(CaseReview(case_file_id=cid, run_seq=1, state="approved", terminal_status="audit_complete",
                         documents_fingerprint="old", decided_at=datetime.datetime.now(datetime.timezone.utc)))
        await s.commit()
    assert await rq.on_terminal(str(cid), "audit_complete", None) is None

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(func.count()).select_from(CaseReview).where(CaseReview.case_file_id == cid))).scalar_one()
        events = (
            await s.execute(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.case_file_id == cid,
                    AnalyticsEvent.event_name == "review_enqueue_skipped_synthetic",
                )
            )
        ).scalars().all()
    assert rows == 1  # only the row this test planted
    assert [e.properties for e in events] == [
        {"terminal": "audit_complete"}, {"terminal": "audit_incomplete"}, {"terminal": "audit_complete"},
    ]
    assert all(e.user_id == uid for e in events)  # attributed to its subject, never anonymous


@pytest.mark.asyncio
async def test_a_real_users_run_still_enqueues():
    admin = await _admin_id()
    async with AsyncSessionLocal() as s:
        await rq.set_sample_pct(s, 100, admin_id=admin)
        await s.commit()
    uid = await _user(f"real{uuid.uuid4().hex[:10]}@example.com")
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status="audit_complete")
        s.add(cf)
        await s.commit()
        cid = cf.case_file_id
    assert await rq.on_terminal(str(cid), "audit_complete", None) is not None


# ── the teardown ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_teardown_removes_everything_for_that_run_tag_and_nothing_else():
    admin = await _admin_id()
    email_a, email_b = _synth_email(), _synth_email()
    a, b = await _user(email_a), await _user(email_b)
    c = await _user(f"real{uuid.uuid4().hex[:10]}@example.com")
    a1, a1_file = await _populated_case(a, admin)
    a2, a2_file = await _populated_case(a, admin)
    b1, b1_file = await _populated_case(b, admin)
    c1, c1_file = await _populated_case(c, admin)
    before_b, before_c = await _footprint(b, [b1]), await _footprint(c, [c1])
    assert (await _footprint(a, [a1, a2]))["case_files"] == 2

    async with AsyncSessionLocal() as s:
        counts = await teardown_synthetic_user(s, email_a.upper())  # case-insensitive match
        await s.commit()

    assert counts["users"] == 1 and counts["case_files"] == 2 and counts["stored_files"] == 2
    gone = await _footprint(a, [a1, a2])
    audit_kept = gone.pop("audit_events")
    assert audit_kept == 2  # the audit log is append-only — never touched
    assert gone == {k: 0 for k in gone}
    assert not a1_file.exists() and not a2_file.exists()
    # …and nothing else: another run's identity and a real user are byte-for-byte as they were
    assert await _footprint(b, [b1]) == before_b and await _footprint(c, [c1]) == before_c
    assert b1_file.exists() and c1_file.exists()


@pytest.mark.asyncio
async def test_teardown_keeps_a_failed_scenarios_case_and_so_the_identity():
    admin = await _admin_id()
    email = _synth_email()
    uid = await _user(email)
    failed, failed_file = await _populated_case(uid, admin)
    passed, passed_file = await _populated_case(uid, admin)

    async with AsyncSessionLocal() as s:
        counts = await teardown_synthetic_user(s, email, keep_case_ids=[str(failed)])
        await s.commit()
    assert counts["kept_cases"] == 1 and counts["case_files"] == 1 and counts["users"] == 0
    assert failed_file.exists() and not passed_file.exists()
    left = await _footprint(uid, [failed])
    assert left["users"] == 1 and left["case_files"] == 1 and left["findings"] == 1 and left["messages"] == 2

    async with AsyncSessionLocal() as s:  # the later pass, without a keep list, finishes the job
        counts = await teardown_synthetic_user(s, email)
        await s.commit()
    assert counts["users"] == 1 and not failed_file.exists()
    async with AsyncSessionLocal() as s:  # idempotent: the identity is simply gone
        assert await teardown_synthetic_user(s, email) == {"users": 0}


@pytest.mark.asyncio
async def test_a_real_identity_can_never_be_passed_through():
    real = f"real{uuid.uuid4().hex[:10]}@example.com"
    uid = await _user(real)
    async with AsyncSessionLocal() as s:
        with pytest.raises(NotSynthetic):
            await teardown_synthetic_user(s, real)
        with pytest.raises(NotSynthetic):
            await teardown_synthetic_user(s, "")
    assert (await _footprint(uid, []))["users"] == 1


@pytest.mark.asyncio
async def test_cleanup_endpoint_is_gated_like_test_token_and_suffix_restricted(
    client: AsyncClient, monkeypatch
):
    admin = await _admin_id()
    email = _synth_email()
    uid = await _user(email)
    cid, stored = await _populated_case(uid, admin)

    # suffix restriction — a real identity is refused before any query runs
    r = await client.post("/v1/admin/test-cleanup", json={"email": "someone@example.com"})
    assert r.status_code == 400 and "synthetic" in r.json()["detail"]
    r = await client.post("/v1/admin/test-cleanup", json={"email": email, "keep_case_ids": ["not-a-uuid"]})
    assert r.status_code == 422

    # the same three gates as test-token: real auth + no session -> 404 (DL-60 reveals nothing);
    # a wrong secret -> 404; production -> 404 even with the right secret
    s = get_settings()
    monkeypatch.setattr(s, "use_real_auth", True)
    monkeypatch.setattr(s, "auth_secret", "x" * 32)
    monkeypatch.setattr(s, "e2e_test_token_secret", "e2e-shared-secret")
    assert (await client.post("/v1/admin/test-cleanup", json={"email": email})).status_code == 404
    wrong = await client.post(
        "/v1/admin/test-cleanup", json={"email": email}, headers={"X-E2E-Test-Secret": "nope"}
    )
    assert wrong.status_code == 404
    monkeypatch.setattr(s, "node_env", "production")
    prod = await client.post(
        "/v1/admin/test-cleanup", json={"email": email}, headers={"X-E2E-Test-Secret": "e2e-shared-secret"}
    )
    assert prod.status_code == 404
    assert stored.exists() and (await _footprint(uid, [cid]))["users"] == 1  # nothing was touched

    monkeypatch.setattr(s, "node_env", "development")
    ok = await client.post(
        "/v1/admin/test-cleanup", json={"email": email}, headers={"X-E2E-Test-Secret": "e2e-shared-secret"}
    )
    assert ok.status_code == 200 and ok.json()["deleted"]["users"] == 1 and not stored.exists()
    again = await client.post(
        "/v1/admin/test-cleanup", json={"email": email}, headers={"X-E2E-Test-Secret": "e2e-shared-secret"}
    )
    assert again.status_code == 200 and again.json()["deleted"] == {"users": 0}  # idempotent


@pytest.mark.asyncio
async def test_every_foreign_key_into_a_deleted_table_is_accounted_for():
    """The teardown deletes in FK order by hand (every FK here is NO ACTION). This introspects
    the LIVE schema: a new table that references users / case_files / … must be added to
    COVERED_FKS (and handled) or this fails — the teardown cannot silently rot."""
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT conrelid::regclass::text, a.attname FROM pg_constraint c "
                    "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) "
                    "WHERE c.contype = 'f' AND confrelid::regclass::text = ANY(:parents)"
                ),
                {"parents": list(DELETED_TABLES)},
            )
        ).all()
    live = {(t, c) for t, c in rows}
    assert live, "introspection returned nothing — the guard would be vacuous"
    missing = sorted(live - set(COVERED_FKS))
    assert not missing, f"FKs the synthetic teardown does not account for: {missing}"
    stale = sorted(set(COVERED_FKS) - live)
    assert not stale, f"COVERED_FKS names FKs that no longer exist: {stale}"
