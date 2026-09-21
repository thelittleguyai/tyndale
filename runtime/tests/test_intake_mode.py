"""Guided intake, item 1 — the `intake_mode` flag (doc 40 §D): who gets which front door,
that the decision is made once, and that every case and every case-scoped event says which
door opened it."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.analytics.emit import emit
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.intake.mode import (
    HIDEABLE_SURFACES,
    cohort_bucket,
    decide_cohort,
    ensure_cohort,
    hidden_surfaces,
    resolve_intake_mode,
)


def _settings(**over):
    base = dict(
        intake_mode_default="chat_first",
        intake_mode_cohort_pct=0,
        guided_hidden_surface_list=["freeform_chat_entry", "quick_actions_grid"],
    )
    return SimpleNamespace(**{**base, **over})


def _user(**over):
    return SimpleNamespace(**{"user_id": uuid.uuid4(), "intake_mode": None, "intake_cohort": None, **over})


# ── the cohort ───────────────────────────────────────────────────────────────────────────
def test_cohort_assignment_is_deterministic_and_roughly_the_asked_share():
    ids = [uuid.UUID(int=i * 7919 + 13) for i in range(4000)]
    assert [cohort_bucket(i) for i in ids] == [cohort_bucket(str(i)) for i in ids]  # stable, str or UUID
    share = sum(decide_cohort(i, cohort_pct=30, is_new=True) == "guided" for i in ids) / len(ids)
    assert 0.26 < share < 0.34
    assert all(decide_cohort(i, cohort_pct=0, is_new=True) == "default" for i in ids[:200])
    assert all(decide_cohort(i, cohort_pct=100, is_new=True) == "guided" for i in ids[:200])


def test_raising_the_dial_only_ever_adds_users_to_the_cohort():
    """Monotonic: nobody who was guided at 10% is un-guided at 50%."""
    ids = [uuid.UUID(int=i) for i in range(1, 1500)]
    at10 = {i for i in ids if decide_cohort(i, cohort_pct=10, is_new=True) == "guided"}
    at50 = {i for i in ids if decide_cohort(i, cohort_pct=50, is_new=True) == "guided"}
    assert at10 and at10 < at50


def test_only_new_users_are_sampled_and_the_decision_is_made_once():
    veteran = _user()
    assert ensure_cohort(veteran, _settings(intake_mode_cohort_pct=100), is_new=False) is True
    assert veteran.intake_cohort == "default"  # has cases already — not the population sampled

    newbie = _user()
    assert ensure_cohort(newbie, _settings(intake_mode_cohort_pct=100), is_new=True) is True
    assert newbie.intake_cohort == "guided"
    # the dial drops to zero next month: a decided user is NOT re-decided
    assert ensure_cohort(newbie, _settings(intake_mode_cohort_pct=0), is_new=True) is False
    assert newbie.intake_cohort == "guided"


def test_resolution_order_is_override_then_cohort_then_default():
    s = _settings(intake_mode_default="chat_first")
    assert resolve_intake_mode(_user(), s) == ("chat_first", "default")
    assert resolve_intake_mode(_user(intake_cohort="guided"), s) == ("guided", "cohort")
    assert resolve_intake_mode(_user(intake_cohort="default"), s) == ("chat_first", "default")
    # the override beats the cohort in BOTH directions
    assert resolve_intake_mode(_user(intake_cohort="guided", intake_mode="chat_first"), s) == ("chat_first", "override")
    assert resolve_intake_mode(_user(intake_cohort="default", intake_mode="guided"), s) == ("guided", "override")
    # flipping the env default moves everyone who is merely 'default'
    assert resolve_intake_mode(_user(intake_cohort="default"), _settings(intake_mode_default="guided")) == ("guided", "default")


def test_hidden_surfaces_are_data_for_guided_users_only_and_unknown_names_are_dropped():
    s = _settings(guided_hidden_surface_list=["freeform_chat_entry", "made_up_surface", "quick_actions_grid"])
    assert hidden_surfaces("chat_first", s) == []  # chat-first: nothing changes
    assert hidden_surfaces("guided", s) == ["freeform_chat_entry", "quick_actions_grid"]
    assert hidden_surfaces("guided", _settings(guided_hidden_surface_list=[])) == []  # the answer can be "hide nothing"
    assert set(hidden_surfaces("guided", s)) <= set(HIDEABLE_SURFACES)


def test_settings_reject_a_mistyped_mode_at_boot():
    from pydantic import ValidationError

    from app.config import Settings

    for field, bad in (("intake_mode_default", "guide"), ("unlock_gate_mode", "free"), ("intake_mode_cohort_pct", 101)):
        with pytest.raises(ValidationError):
            Settings(**{field: bad})
    assert Settings(guided_hidden_surfaces=" Quick_Actions_Grid, ,quick_actions_grid ").guided_hidden_surface_list == ["quick_actions_grid"]


# ── the dashboard tells the client ───────────────────────────────────────────────────────
async def _dev_user_row(**fields) -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        row = (await s.execute(select(User).where(User.user_id == u.user_id))).scalar_one()
        for k, v in fields.items():
            setattr(row, k, v)
        await s.commit()
        return u.user_id


@pytest.mark.asyncio
async def test_dashboard_carries_the_resolved_mode_and_what_to_leave_out(client: AsyncClient):
    try:
        await _dev_user_row(intake_mode="guided", intake_cohort="default")
        body = (await client.get("/v1/dashboard")).json()
        assert (body["intake_mode"], body["intake_mode_source"]) == ("guided", "override")
        assert body["hidden_surfaces"] == ["freeform_chat_entry", "quick_actions_grid"]

        await _dev_user_row(intake_mode=None)
        body = (await client.get("/v1/dashboard")).json()
        assert (body["intake_mode"], body["intake_mode_source"]) == ("chat_first", "default")
        assert body["hidden_surfaces"] == []
    finally:
        await _dev_user_row(intake_mode=None, intake_cohort="default")


@pytest.mark.asyncio
async def test_admin_can_override_and_clear_a_users_mode_and_it_is_audit_logged(client: AsyncClient):
    uid = await _dev_user_row(intake_mode=None, intake_cohort="default")
    try:
        r = await client.post(f"/v1/admin/users/{uid}/set-intake-mode", json={"intake_mode": "guided"})
        assert r.status_code == 200, r.text
        assert r.json()["intake_mode"] == {"override": "guided", "cohort": "default", "resolved": "guided", "source": "override"}
        detail = (await client.get(f"/v1/admin/users/{uid}")).json()
        assert detail["intake_mode"]["resolved"] == "guided"

        r = await client.post(f"/v1/admin/users/{uid}/set-intake-mode", json={"intake_mode": None})
        assert r.json()["intake_mode"]["source"] == "default"
        assert (await client.post(f"/v1/admin/users/{uid}/set-intake-mode", json={"intake_mode": "wizard"})).status_code == 422

        async with AsyncSessionLocal() as s:
            rows = (await s.execute(select(AuditEvent).where(AuditEvent.user_id == uid).order_by(AuditEvent.timestamp.desc()).limit(6))).scalars().all()
        from app.routes.admin._deps import decode_payload

        assert "set_intake_mode" in [decode_payload(e).get("action") for e in rows]
    finally:
        await _dev_user_row(intake_mode=None, intake_cohort="default")


# ── every case, and every case-scoped event, says which door opened it ────────────────────
@pytest.mark.asyncio
async def test_every_case_scoped_event_is_stamped_with_its_cases_front_door():
    uid = await _dev_user_row()
    async with AsyncSessionLocal() as s:
        guided = CaseFile(user_id=uid, status="open", intake_mode="guided")
        legacy = CaseFile(user_id=uid, status="open")  # the server default
        s.add_all([guided, legacy])
        await s.commit()
        gid, lid = guided.case_file_id, legacy.case_file_id
    assert await emit("upload_started", user_id=uid, case_file_id=gid, properties={"file_count": 1})
    assert await emit("upload_started", user_id=uid, case_file_id=lid, properties={"file_count": 2})
    assert await emit("upload_started", user_id=uid, properties={"file_count": 3})  # not case-scoped
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(AnalyticsEvent).where(AnalyticsEvent.user_id == uid).where(AnalyticsEvent.event_name == "upload_started").order_by(AnalyticsEvent.occurred_at.desc()).limit(3))).scalars().all()
    by_count = {r.properties["file_count"]: r for r in rows}
    assert by_count[1].intake_mode == "guided"
    assert by_count[2].intake_mode == "chat_first"
    assert by_count[3].intake_mode is None
    assert by_count[1].properties == {"file_count": 1}  # the call site's payload is untouched


@pytest.mark.asyncio
async def test_the_review_queue_shows_and_filters_by_front_door(client: AsyncClient):
    import datetime

    from app.review import queue as rq

    uid = await _dev_user_row()
    async with AsyncSessionLocal() as s:
        await rq.set_sample_pct(s, 100, admin_id=uid)
        cf = CaseFile(user_id=uid, status="audit_complete", intake_mode="guided")
        s.add(cf)
        await s.commit()
        cfid = str(cf.case_file_id)
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    rid = await rq.on_terminal(cfid, "audit_complete", None)
    assert rid
    guided = (await client.get("/v1/admin/review/queue", params={"limit": 200, "since": since, "intake_mode": "guided"})).json()["items"]
    row = next(i for i in guided if i["review_id"] == rid)
    assert row["intake_mode"] == "guided"
    other = (await client.get("/v1/admin/review/queue", params={"limit": 200, "since": since, "intake_mode": "chat_first"})).json()["items"]
    assert all(i["review_id"] != rid for i in other)
    assert (await client.get("/v1/admin/review/queue", params={"intake_mode": "wizard"})).status_code == 422
    ws = (await client.get(f"/v1/admin/review/cases/{cfid}")).json()
    assert ws["case"]["intake_mode"] == "guided"  # the workspace header agrees
