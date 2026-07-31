"""Analytics event infrastructure (Internal Analytics P0). Rule 2 — PHI-free by construction — is
the heart: the validator accepts only enums/numbers/booleans, so an un-enumerated string can never
be stored. Also covers the batch endpoint's silent-drop-with-counter behavior and the outcome
idempotency mechanism (emit_idempotent)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.analytics.emit import emit, emit_idempotent
from app.analytics.events import (
    REGISTRY,
    EventValidationError,
    PropType,
    validate_event,
)
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.users import User


# --- Rule 2: PHI-free validation (pure) -------------------------------------
def test_rejects_unregistered_event_name():
    with pytest.raises(EventValidationError):
        validate_event("definitely_not_a_registered_event", {})


def test_rejects_unregistered_property():
    with pytest.raises(EventValidationError):
        validate_event("audit_started", {"surprise": 1})


def test_rejects_free_text_where_enum_expected():
    # verification_answered.answer is an enum; an arbitrary string (potential free text/PHI) fails.
    with pytest.raises(EventValidationError):
        validate_event("verification_answered", {"answer": "the patient said hi", "question_position": 1})


def test_rejects_string_where_number_expected():
    with pytest.raises(EventValidationError):
        validate_event("stage_completed", {"stage": "audit", "duration_ms": "12ms"})


def test_rejects_bool_masquerading_as_number():
    with pytest.raises(EventValidationError):
        validate_event("upload_started", {"file_count": True})


def test_accepts_well_formed_event_and_normalizes():
    out = validate_event("verification_answered", {"answer": "not_sure", "question_position": 2})
    assert out == {"answer": "not_sure", "question_position": 2.0}


def test_every_wired_call_site_payload_is_valid():
    """The exact payloads the server-side call sites emit must pass validation — a wrong name or
    property would otherwise be silently dropped. Keep in lockstep with the emit call sites."""
    for name, props in [
        ("audit_started", {}),
        ("audit_completed", {}),
        ("audit_needs_documents", {}),
        ("audit_system_error", {}),
        ("document_request_issued", {}),
        ("document_request_satisfied", {}),
        ("outcome_reported", {"resolved": "yes", "amount_saved": 400.0}),
        ("finding_feedback", {"thumbs": "down"}),
        ("upload_started", {"file_count": 1}),
        ("documents_accepted", {"doc_count": 1}),
        ("extraction_succeeded", {"doc_type": "eob"}),
        ("verification_answered", {"answer": "not_sure", "question_position": 1}),
        ("nudge_sent", {"stage": "first"}),
        ("consent_opt_in", {}),
        ("consent_withdrawn", {}),
        ("deletion_requested", {}),
        ("deletion_completed", {"hours_to_complete": 0.0}),
        ("crisis_fire_count", {}),
        ("refusal_event", {"category": "other"}),
        ("mapper_suggested", {}),
        ("mapper_fallback", {"kind": "partial"}),
        ("mapper_fallback", {"kind": "full"}),
        ("stage_completed", {"stage": "audit", "duration_ms": 1234.0}),
    ]:
        validate_event(name, props)  # raises EventValidationError if a call site drifts


def test_registry_is_phi_free_by_construction():
    # No property type is a free string: the only string-valued type is ENUM with a closed set.
    for name, spec in REGISTRY.items():
        for key, pspec in spec.props.items():
            if pspec.type is PropType.ENUM:
                assert pspec.values, f"{name}.{key} enum has no values"
            else:
                assert pspec.type in (PropType.NUMBER, PropType.BOOLEAN)
                assert pspec.values == (), f"{name}.{key} non-enum carries values"


# --- emit + idempotency (DB) ------------------------------------------------
async def _a_user_id() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User.user_id).limit(1))).scalar_one()


async def _count(event_name: str, dedupe_key: str | None = None) -> int:
    async with AsyncSessionLocal() as s:
        q = select(func.count()).select_from(AnalyticsEvent).where(
            AnalyticsEvent.event_name == event_name
        )
        if dedupe_key is not None:
            q = q.where(AnalyticsEvent.dedupe_key == dedupe_key)
        return (await s.execute(q)).scalar_one()


@pytest.mark.asyncio
async def test_emit_writes_a_validated_row(client: AsyncClient):
    uid = await _a_user_id()
    ok = await emit("audit_started", user_id=uid)
    assert ok is True
    assert await _count("audit_started") >= 1


@pytest.mark.asyncio
async def test_emit_swallows_invalid_and_never_raises(client: AsyncClient):
    uid = await _a_user_id()
    # A free-text value must not raise into the caller; it's dropped.
    ok = await emit("refusal_event", user_id=uid, properties={"category": "free text here"})
    assert ok is False


@pytest.mark.asyncio
async def test_outcome_capture_is_idempotent(client: AsyncClient):
    """P0 (Brock): a double-tapped outcome button can never double-report."""
    uid = await _a_user_id()
    cid = uuid.uuid4()
    key = f"outcome_reported:{cid}"
    props = {"resolved": "yes", "amount_saved": 400.0}
    await emit_idempotent("outcome_reported", dedupe_key=key, user_id=uid, case_file_id=cid, properties=props)
    await emit_idempotent("outcome_reported", dedupe_key=key, user_id=uid, case_file_id=cid, properties=props)
    await emit_idempotent("outcome_reported", dedupe_key=key, user_id=uid, case_file_id=cid, properties=props)
    assert await _count("outcome_reported", dedupe_key=key) == 1  # exactly one, despite three fires


# --- POST /v1/events (batch endpoint) ---------------------------------------
@pytest.mark.asyncio
async def test_batch_drops_unknown_and_server_only_accepts_client_event(client: AsyncClient):
    r = await client.post(
        "/v1/events",
        json={
            "events": [
                {"name": "not_a_real_event", "properties": {}},  # unknown → dropped
                {"name": "upload_started", "properties": {"file_count": 1}},  # server_only → dropped
                {"name": "call_step_viewed", "properties": {"step_index": 0}},  # client-ok → accepted
            ]
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] == 1 and body["dropped"] == 2


@pytest.mark.asyncio
async def test_batch_drops_nonconforming_properties(client: AsyncClient):
    # call_step_viewed.step_index is a number; a string is dropped (never stored as free text).
    r = await client.post(
        "/v1/events",
        json={"events": [{"name": "call_step_viewed", "properties": {"step_index": "one"}}]},
    )
    assert r.status_code == 200
    assert r.json() == {"accepted": 0, "dropped": 1}


# --- Ownership guard (July 20 audit): cross-tenant attribution impossible ----
async def _authed_uid(client: AsyncClient) -> uuid.UUID:
    """The uid the batch endpoint attributes rows to (dev auth stub)."""
    await client.post(
        "/v1/events", json={"events": [{"name": "call_step_viewed", "properties": {"step_index": 9}}]}
    )
    async with AsyncSessionLocal() as s:
        return (
            await s.execute(
                select(AnalyticsEvent.user_id)
                .where(AnalyticsEvent.event_name == "call_step_viewed")
                .order_by(AnalyticsEvent.occurred_at.desc())
                .limit(1)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_batch_drops_events_claiming_a_case_the_user_does_not_own(client: AsyncClient):
    from app.db.models.case_files import CaseFile

    me = await _authed_uid(client)
    async with AsyncSessionLocal() as s:
        other = User(email=f"other-{uuid.uuid4().hex[:10]}@example.test")
        s.add(other)
        await s.flush()
        theirs = CaseFile(user_id=other.user_id, status="audit_running")
        mine = CaseFile(user_id=me, status="audit_running")
        s.add_all([theirs, mine])
        await s.commit()
        their_case, my_case = theirs.case_file_id, mine.case_file_id

    r = await client.post(
        "/v1/events",
        json={
            "events": [
                # someone else's case → dropped (never attributed cross-tenant)
                {"name": "call_step_viewed", "properties": {"step_index": 1}, "case_file_id": str(their_case)},
                # nonexistent case → dropped (ownership unverifiable; anti-enumeration: same 200)
                {"name": "call_step_viewed", "properties": {"step_index": 2}, "case_file_id": str(uuid.uuid4())},
                # my own case → accepted
                {"name": "call_step_viewed", "properties": {"step_index": 3}, "case_file_id": str(my_case)},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"accepted": 1, "dropped": 2}

    async with AsyncSessionLocal() as s:
        cross = (
            await s.execute(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.case_file_id == their_case)
            )
        ).scalar_one()
        owned = (
            await s.execute(
                select(func.count())
                .select_from(AnalyticsEvent)
                .where(AnalyticsEvent.case_file_id == my_case)
                .where(AnalyticsEvent.user_id == me)
            )
        ).scalar_one()
    assert cross == 0  # not one row ever landed on the other tenant's case
    assert owned == 1
