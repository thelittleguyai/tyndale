"""Human Review Phase 1 — the admin review API (doc 39 §1–§2 as amended by §7): queue +
health strip, the dial, the four-tab workspace (with its view audit event), and the three
verdict actions with their validation."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CaseReview
from app.db.models.findings import Finding
from app.review import queue as rq


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


async def _finding(case_file_id: str, **over) -> str:
    async with AsyncSessionLocal() as s:
        f = Finding(
            case_file_id=uuid.UUID(case_file_id),
            finding_type=over.get("finding_type", "provider_side"),
            category=over.get("category", "bundling"),
            subagent_source="bill_detective",
            voice_tier="B",
            facts=over.get(
                "facts",
                {"gap": 120.0, "notes": "99284 billed alongside its component", "codes": ["99284"]},
            ),
            legal_claim=over.get(
                "legal_claim",
                {"claim": "NCCI bundles the component into the primary code.", "citations": []},
            ),
            recommendation=over.get(
                "recommendation",
                {"action": "Ask billing to remove the bundled line.", "reasoning": "NCCI edit"},
            ),
            status="open",
        )
        s.add(f)
        await s.commit()
        return str(f.finding_id)


async def _enqueued(**fields) -> tuple[str, str]:
    await _set_dial(100)
    cfid = await _case(**fields)
    rid = await rq.on_terminal(cfid, "audit_complete", None)
    assert rid
    return cfid, rid


async def _audit_actions(cfid: str) -> list[str]:
    async with AsyncSessionLocal() as s:
        rows = (
            (
                await s.execute(
                    select(AuditEvent)
                    .where(AuditEvent.case_file_id == uuid.UUID(cfid))
                    .where(AuditEvent.event_type == "user_action")
                )
            )
            .scalars()
            .all()
        )
    return [json.loads(bytes(a.payload_encrypted).decode()).get("action") for a in rows]


_DISAPPROVE = {
    "action": "disapprove",
    "verdict_type": "missed_finding",
    "scope": "whole_case",
    "cause": "content_gap",
    "structured_note": {
        "concluded": "no finding on the bundled line",
        "should_have_concluded": "NCCI bundling finding",
        "input_or_rule": "ncci edit table missing the 99284 pair",
    },
}


# ── queue ───────────────────────────────────────────────────────────────────────────────


def _just_now() -> str:
    """ISO timestamp a minute ago — the queue's `since` filter. The shared local DB accumulates
    pending rows across runs and the queue lists oldest-first, so without it a freshly enqueued
    row falls off `limit=200` and the listing tests fail for reasons unrelated to the code."""
    import datetime

    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()


@pytest.mark.asyncio
async def test_queue_lists_run_with_masked_user_and_health(client: AsyncClient):
    since = _just_now()
    cfid, rid = await _enqueued()
    r = await client.get(
        "/v1/admin/review/queue",
        params={"state": "unreviewed,re_review,in_review", "limit": 200, "since": since},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    item = next(i for i in body["items"] if i["review_id"] == rid)
    assert item["case_file_id"] == cfid and item["state"] == "unreviewed"
    assert item["user_masked"].startswith("u·") and len(item["user_masked"]) == 6
    assert "email" not in item and "user_id" not in item
    assert set(item["flags"]) == {"first_case", "system_error", "canary", "material_disagreement"}
    h = body["health"]
    for k in (
        "unreviewed",
        "in_review",
        "median_age_hours",
        "approval_rate_7d",
        "approval_rate_30d",
    ):
        assert k in h


@pytest.mark.asyncio
async def test_queue_filters_and_rejects_unknown_values(client: AsyncClient):
    assert (
        await client.get("/v1/admin/review/queue", params={"state": "bogus"})
    ).status_code == 422
    assert (
        await client.get("/v1/admin/review/queue", params={"confidence": "sky-high"})
    ).status_code == 422
    since = _just_now()
    cfid = await _case(status="audit_incomplete", audit_incomplete_reason="system_error")
    rid = await rq.on_terminal(cfid, "audit_incomplete", "system_error")
    hits = (
        await client.get(
            "/v1/admin/review/queue",
            params={"has_system_error": "true", "limit": 200, "since": since},
        )
    ).json()["items"]
    assert any(i["review_id"] == rid for i in hits)
    misses = (
        await client.get(
            "/v1/admin/review/queue",
            params={"has_system_error": "false", "limit": 200, "since": since},
        )
    ).json()["items"]
    assert all(i["review_id"] != rid for i in misses)


@pytest.mark.asyncio
async def test_settings_dial_roundtrip(client: AsyncClient):
    try:
        assert (await client.get("/v1/admin/review/settings")).json()["review_sample_pct"] in range(
            0, 101
        )
        assert (
            await client.put("/v1/admin/review/settings", json={"review_sample_pct": 40})
        ).status_code == 200
        got = (await client.get("/v1/admin/review/settings")).json()
        assert got["review_sample_pct"] == 40 and set(got["triggers"]) == {
            "first_case",
            "low_confidence",
            "system_error",
            "canary",
            "material_disagreement",
        }
        assert (
            await client.put("/v1/admin/review/settings", json={"review_sample_pct": 101})
        ).status_code == 422
    finally:
        await _set_dial(100)


# ── workspace ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workspace_assembles_four_tabs_without_claiming_and_audits_the_view(
    client: AsyncClient,
):
    cfid, rid = await _enqueued(
        documents=[{"document_type": "bill", "filename": "a.pdf", "ocr_text": "x" * 40}],
        eobs=[{"document_type": "eob", "filename": "e.pdf", "ocr_text": "y" * 7}],
    )
    fid = await _finding(cfid)
    r = await client.get(f"/v1/admin/review/cases/{cfid}")
    assert r.status_code == 200, r.text
    ws = r.json()
    assert set(ws["tabs"]) == {"analysis", "conversation", "results", "provenance"}
    # deep review: a GET (a view, a prefetch, a colleague glancing) must NOT claim the row
    assert ws["review"]["review_id"] == rid and ws["review"]["state"] == "unreviewed"
    assert ws["review"]["reviewer_masked"] is None
    assert ws["case"]["user_masked"].startswith("u·")

    # left pane: document CARDS (no OCR text), extraction, journey
    doc = ws["left"]["documents"][0]
    assert doc["document_type"] == "bill" and doc["text_chars"] == 40 and "ocr_text" not in doc
    assert doc["has_text"] is True and (doc["kind"], doc["doc_index"], doc["index"]) == ("document", 0, 0)
    # ONE namespace across documents and eobs — both lists used to start at index 0
    eob = ws["left"]["eobs"][0]
    assert (eob["kind"], eob["doc_index"], eob["index"]) == ("eob", 1, 0) and eob["text_chars"] == 7
    assert "line_items" in ws["left"]["extraction"] and isinstance(ws["left"]["journey"], list)

    # analysis: the finding with basis codes, citations, and the five 'why' lines from EXISTING facts
    f = next(x for x in ws["tabs"]["analysis"]["findings"] if x["finding_id"] == fid)
    assert (
        f["basis_codes"] == ["99284"]
        and f["amount_usd"] == 120.0
        and f["responsible_party"] == "either"
    )
    why = {line["key"]: line["value"] for line in f["why"]}
    assert list(why) == [
        "observed", "rule", "numbers", "action", "producer", "rule_effective_date", "confidence",
    ]
    assert why["observed"] == "99284 billed alongside its component"
    assert why["numbers"] == {"gap": 120.0}
    assert why["producer"] == "bill_detective · tier B"

    # results: the same gameplan builder the app uses, tiers, identifiers, outcomes
    assert ws["tabs"]["results"]["gameplan"][0]["finding_id"] == fid
    assert ws["tabs"]["results"]["tiers"][0]["voice_tier"] == "B"
    assert set(ws["tabs"]["results"]["identifiers"]) == {
        "claim_number",
        "account_number",
        "provider_phone",
        "payer_phone",
    }
    assert isinstance(ws["tabs"]["conversation"], list)

    # provenance: existing sections + Phase 2 placeholders, labeled — never faked
    prov = ws["tabs"]["provenance"]
    for k in (
        "tools_called",
        "qdrant_chunks_retrieved",
        "subagent_calls",
        "llm_calls",
        "findings_written",
        "tripwires",
    ):
        assert k in prov
    for k in ("api_pulls", "live_lookups", "missing_data", "retrieval_misses"):
        assert prov[k]["status"] == "coming_in_phase_2"

    # "never the OCR text": the provenance tab carries the same text-free cards, not raw entries
    assert [d["doc_index"] for d in prov["documents"]] == [0, 1]
    assert all("ocr_text" not in d and "ocr_text_preview" not in d for d in prov["documents"])
    assert "x" * 40 not in r.text and "y" * 7 not in r.text  # nowhere in the payload

    assert "review_view" in await _audit_actions(cfid)
    again = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    assert again["review"]["state"] == "unreviewed" and len(again["review_chain"]) == 1


@pytest.mark.asyncio
async def test_why_lines_render_null_when_not_recorded(client: AsyncClient):
    cfid, _ = await _enqueued()
    await _finding(cfid, facts={"gap": 5.0}, legal_claim=None, recommendation=None)
    ws = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    why = {line["key"]: line["value"] for line in ws["tabs"]["analysis"]["findings"][0]["why"]}
    assert why["observed"] is None and why["rule"] is None and why["action"] is None
    assert why["rule_effective_date"] is None and why["confidence"] is None  # "not recorded"


@pytest.mark.asyncio
async def test_workspace_404s_unknown_case(client: AsyncClient):
    assert (await client.get(f"/v1/admin/review/cases/{uuid.uuid4()}")).status_code == 404


# ── verdicts ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disapprove_rejects_missing_cause_scope_and_note(client: AsyncClient):
    cfid, _ = await _enqueued()
    r = await client.post(
        f"/v1/admin/review/cases/{cfid}/verdict",
        json={"action": "disapprove", "verdict_type": "wrong"},
    )
    assert r.status_code == 422
    detail = " ".join(r.json()["detail"])
    assert "scope" in detail and "cause" in detail and "structured_note" in detail

    r = await client.post(
        f"/v1/admin/review/cases/{cfid}/verdict", json={**_DISAPPROVE, "scope": "findings"}
    )
    assert r.status_code == 422 and "target finding" in " ".join(r.json()["detail"])

    r = await client.post(
        f"/v1/admin/review/cases/{cfid}/verdict", json={**_DISAPPROVE, "cause": "vibes"}
    )
    assert r.status_code == 422 and "cause" in " ".join(r.json()["detail"])

    r = await client.post(
        f"/v1/admin/review/cases/{cfid}/verdict",
        json={**_DISAPPROVE, "verdict_type": "unable_to_verify"},
    )
    assert r.status_code == 422

    empty_note = {
        **_DISAPPROVE,
        "structured_note": {**_DISAPPROVE["structured_note"], "input_or_rule": "  "},
    }
    r = await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json=empty_note)
    assert r.status_code == 422 and "input_or_rule" in " ".join(r.json()["detail"])

    # nothing was written by the rejected attempts
    async with AsyncSessionLocal() as s:
        assert (
            await s.execute(
                select(AdminVerdict).where(AdminVerdict.case_file_id == uuid.UUID(cfid))
            )
        ).scalars().all() == []


@pytest.mark.asyncio
async def test_disapprove_stores_cause_structured_note_and_scope(client: AsyncClient):
    cfid, rid = await _enqueued()
    fid = await _finding(cfid)
    body = {**_DISAPPROVE, "scope": "findings", "target_findings": [fid], "note": "analyst note"}
    r = await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["state"] == "disapproved"
        and out["cause"] == "content_gap"
        and out["phase2_route"] == "rule_candidate"
    )
    async with AsyncSessionLocal() as s:
        v = await s.get(AdminVerdict, uuid.UUID(out["verdict_id"]))
        row = await s.get(CaseReview, uuid.UUID(rid))
    assert v.verdict == "missed_finding" and v.cause == "content_gap" and v.target_findings == [fid]
    assert v.structured_note == _DISAPPROVE["structured_note"] and v.notes == "analyst note"
    assert (
        row.state == "disapproved" and row.verdict_id == v.verdict_id and row.decided_at is not None
    )
    assert "review_verdict" in await _audit_actions(cfid)
    async with AsyncSessionLocal() as s:
        ev = (
            (
                await s.execute(
                    select(AnalyticsEvent)
                    .where(AnalyticsEvent.case_file_id == uuid.UUID(cfid))
                    .where(AnalyticsEvent.event_name == "review_verdict_recorded")
                )
            )
            .scalars()
            .all()
        )
    assert ev and ev[-1].properties == {
        "action": "disapprove",
        "cause": "content_gap",
        "scope": "findings",
        "findings_in_scope": 1,
    }


@pytest.mark.asyncio
async def test_approve_then_cant_verify_is_append_only(client: AsyncClient):
    cfid, rid = await _enqueued()
    r = await client.post(
        f"/v1/admin/review/cases/{cfid}/verdict", json={"action": "approve", "note": "looks right"}
    )
    assert (
        r.status_code == 200
        and r.json()["state"] == "approved"
        and r.json()["verdict"] == "correct"
    )
    first_vid = r.json()["verdict_id"]

    r = await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json={"action": "cant_verify"})
    assert (
        r.status_code == 200
        and r.json()["state"] == "cant_verify"
        and r.json()["verdict"] == "unable_to_verify"
    )
    assert r.json()["review_id"] != rid  # a decided run gets a NEW linked row, never an overwrite

    async with AsyncSessionLocal() as s:
        verdicts = (
            (
                await s.execute(
                    select(AdminVerdict).where(AdminVerdict.case_file_id == uuid.UUID(cfid))
                )
            )
            .scalars()
            .all()
        )
        rows = (
            (
                await s.execute(
                    select(CaseReview)
                    .where(CaseReview.case_file_id == uuid.UUID(cfid))
                    .order_by(CaseReview.run_seq)
                )
            )
            .scalars()
            .all()
        )
    assert {str(v.verdict_id) for v in verdicts} >= {first_vid} and len(verdicts) == 2
    assert [x.state for x in rows] == ["approved", "cant_verify"]
    assert rows[1].prior_review_id == rows[0].review_id and str(rows[0].verdict_id) == first_vid

    ws = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    assert [v["verdict"] for v in ws["verdicts"]] == ["unable_to_verify", "correct"]
    assert ws["review"]["state"] == "cant_verify"  # a decided row is never downgraded by a view



# ══ deep review (2026-09-18): claim on intent, the reviewer's two missing lines, the summary ══


@pytest.mark.asyncio
async def test_claim_is_explicit_idempotent_and_never_steals(client: AsyncClient):
    from app.auth import CurrentUser, current_user
    from app.db.models.users import User
    from app.main import app

    cfid, rid = await _enqueued()
    first = await client.post(f"/v1/admin/review/cases/{cfid}/claim")
    assert first.status_code == 200, first.text
    assert first.json() == {
        "review_id": rid, "state": "in_review", "claimed": True, "held_by_me": True,
        "reviewer_masked": first.json()["reviewer_masked"],
    }
    assert first.json()["reviewer_masked"].startswith("u\u00b7")
    again = (await client.post(f"/v1/admin/review/cases/{cfid}/claim")).json()
    assert again["claimed"] is False and again["held_by_me"] is True and again["state"] == "in_review"
    assert (await _audit_actions(cfid)).count("review_claim") == 1  # the no-op wrote nothing

    async with AsyncSessionLocal() as s:  # a second, real admin
        other = User(email=f"adm{uuid.uuid4().hex[:8]}@example.com", user_type="admin")
        s.add(other)
        await s.commit()
        other_id = other.user_id
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=other_id, email="other-admin@example.com", first_name="Other", user_type="admin"
    )
    try:
        theirs = (await client.post(f"/v1/admin/review/cases/{cfid}/claim")).json()
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert theirs["claimed"] is False and theirs["held_by_me"] is False
    assert theirs["reviewer_masked"] == first.json()["reviewer_masked"]  # told who holds it
    async with AsyncSessionLocal() as s:
        row = await s.get(CaseReview, uuid.UUID(rid))
    assert row.reviewer_id != other_id and row.state == "in_review"

    # a decided row is never downgraded by a claim; a case with no row is a 404
    await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json={"action": "approve"})
    decided = (await client.post(f"/v1/admin/review/cases/{cfid}/claim")).json()
    assert decided["state"] == "approved" and decided["claimed"] is False
    assert (await client.post(f"/v1/admin/review/cases/{await _case()}/claim")).status_code == 404


@pytest.mark.asyncio
async def test_why_lines_carry_the_rule_effective_date_and_the_confidence(client: AsyncClient):
    """The two lines that let a reviewer tell stale_data_source from reasoning_error."""
    cfid, _ = await _enqueued()
    from_citation = await _finding(
        cfid,
        facts={"gap": 10.0},
        legal_claim={"claim": "NSA applies", "confidence": 0.7,
                     "citations": [{"authority": "NSA", "src_id": "src_1", "effective_date": "2022-01-01"}]},
    )
    direct = await _finding(cfid, facts={"gap": 1.0, "rule_effective_date": "2024-01-01", "confidence": 0.9})
    ws = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    by_id = {f["finding_id"]: f for f in ws["tabs"]["analysis"]["findings"]}
    why = {line["key"]: line["value"] for line in by_id[from_citation]["why"]}
    assert why["rule_effective_date"] == "2022-01-01" and why["confidence"] == 0.7
    assert by_id[from_citation]["confidence"] == 0.7
    why = {line["key"]: line["value"] for line in by_id[direct]["why"]}
    assert why["rule_effective_date"] == "2024-01-01" and why["confidence"] == 0.9


@pytest.mark.asyncio
async def test_the_reviewer_sees_the_summary_the_user_read(client: AsyncClient):
    from app.agents import orchestrator

    cfid, _ = await _enqueued()
    assert (await client.get(f"/v1/admin/review/cases/{cfid}")).json()["tabs"]["analysis"]["summary"] == ""
    await orchestrator._persist_summary(cfid, "We found a bundling problem worth about $120.")
    ws = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    assert ws["tabs"]["analysis"]["summary"] == "We found a bundling problem worth about $120."
    # the user's own re-fetch reads the same persisted text (the dev user owns this case)
    assert (await client.get(f"/v1/audit/{cfid}")).json()["summary"] == ws["tabs"]["analysis"]["summary"]
    # a fresh compose still wins over the stored one, and a degraded re-run REPLACES it with ""
    assert (await orchestrator._assemble_result(cfid, "fresh")).summary == "fresh"
    await orchestrator._persist_summary(cfid, "")
    assert (await orchestrator._assemble_result(cfid, "")).summary == ""


@pytest.mark.asyncio
async def test_verdict_event_names_the_case_owner_as_subject_and_the_admin_as_actor(client: AsyncClient):
    from app.db.models.users import User

    async with AsyncSessionLocal() as s:
        patient = User(email=f"pt{uuid.uuid4().hex[:10]}@example.com", user_type="user")
        s.add(patient)
        await s.flush()
        cf = CaseFile(user_id=patient.user_id, status="audit_complete")
        s.add(cf)
        await s.commit()
        cfid, patient_id = str(cf.case_file_id), patient.user_id
    r = await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json={"action": "approve"})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        ev = (
            await s.execute(
                select(AnalyticsEvent)
                .where(AnalyticsEvent.case_file_id == uuid.UUID(cfid))
                .where(AnalyticsEvent.event_name == "review_verdict_recorded")
            )
        ).scalar_one()
    admin_id = await _dev_admin_id()
    assert ev.user_id == patient_id and ev.actor_user_id == admin_id and patient_id != admin_id


def test_no_rollup_metric_is_built_on_an_admin_actor_event():
    """'Check the rollup cron treats it correctly': the daily metrics are per-event-name counts
    and ratios; none may be defined over the reviewer's verdict event, whose actor is an
    operator, not a product user."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app/analytics/definitions.py").read_text()
    assert "review_verdict_recorded" not in src and "review_enqueue_skipped_synthetic" not in src


@pytest.mark.asyncio
async def test_every_review_route_is_a_404_for_a_non_admin(client: AsyncClient):
    """DL-60: the console's existence is never revealed."""
    from app.auth import CurrentUser, current_user
    from app.main import app

    cfid, _ = await _enqueued()
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid.uuid4(), email="regular@example.com", first_name="Reg", user_type="user"
    )
    try:
        calls = [
            await client.get("/v1/admin/review/queue"),
            await client.get("/v1/admin/review/settings"),
            await client.put("/v1/admin/review/settings", json={"review_sample_pct": 5}),
            await client.get(f"/v1/admin/review/cases/{cfid}"),
            await client.post(f"/v1/admin/review/cases/{cfid}/claim"),
            await client.post(f"/v1/admin/review/cases/{cfid}/verdict", json={"action": "approve"}),
            await client.post(f"/v1/admin/cases/{cfid}/verdict", json={"verdict": "correct"}),
        ]
    finally:
        app.dependency_overrides.pop(current_user, None)
    assert [c.status_code for c in calls] == [404] * len(calls)
    async with AsyncSessionLocal() as s:  # and nothing was written
        assert (await s.execute(select(AdminVerdict).where(AdminVerdict.case_file_id == uuid.UUID(cfid)))).scalars().all() == []
    assert (await client.get("/v1/admin/review/settings")).json()["review_sample_pct"] == 100
