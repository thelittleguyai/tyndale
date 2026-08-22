"""External-program handoff + access-request intake stub (§A2 state 5 / script §12).

Two properties: the handoff keeps the case OPEN (X1 — a warm handoff is not a hand-off-and-
drop), and the access-request intake DISCLOSES NOTHING while still recording the request
through the encrypted envelope.
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agents.context_loader import load_orchestration_registry, orchestration_step
from app.analytics.events import REGISTRY, PropType
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.security.audit_crypto import decrypt_payload

_X1 = None


def _x1():
    global _X1
    if _X1 is None:
        import importlib.util
        import pathlib
        import sys

        p = (
            pathlib.Path(__file__).resolve().parents[2]
            / "intelligence-layer/evals/doctrine/x1_close_the_loop.py"
        )
        spec = importlib.util.spec_from_file_location("x1_close_the_loop", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["x1_close_the_loop"] = mod
        spec.loader.exec_module(mod)
        _X1 = mod
    return _X1


# --- handoff -----------------------------------------------------------------
@pytest.mark.parametrize("key", ["handoff.pace", "handoff.generic_program"])
def test_handoff_keys_exist(key):
    assert key in load_orchestration_registry()


def test_pace_handoff_promises_tyndale_keeps_the_case_open():
    """§12.1's requirement, and what keeps the handoff X1-compliant: the case stays open.
    B5 (Brock 2026-08-18): §12.1 is [B] — the program source rides as the citation."""
    text = orchestration_step(
        "handoff.pace", citation={"source": "42 CFR 460"},
        program_name="PACE", program_source="42 CFR 460",
    )
    assert "PACE" in text
    assert "keep your case open" in text.lower()


def test_handoff_thread_entry_satisfies_x1():
    """A handoff message names a next step AND keeps the case open — X1 holds over the thread
    (an information_request in this thread would still need its return path)."""
    x1 = _x1()
    thread = [
        {
            "role": "system",
            "kind": "system_message",
            "content": orchestration_step("handoff.pace"),
            "payload": {"handoff": {"program": "pace", "case_stays_open": True}},
        }
    ]
    verdict = x1.check_x1(thread, case_status="audit_complete", nudge_state={"eligible": True})
    assert verdict.passed, verdict.summary()


def test_generic_program_interpolates_his_variables():
    out = orchestration_step(
        "handoff.generic_program", citation={"source": "42 CFR 460"},
        program_name="PACE", program_source="42 CFR 460",
    )
    assert "PACE" in out and "42 CFR 460" in out and "{" not in out


def test_handoff_without_a_program_source_degrades_rather_than_claiming_one():
    """His §12.1 is [A]/[B] and cites the program. With no citation available the string
    degrades — never a sourceless program claim."""
    out = orchestration_step("handoff.generic_program", program_name="PACE", program_source=None)
    assert "{" not in out and out


def test_handoff_analytics_is_an_enum_not_a_program_name():
    spec = REGISTRY["program_handoff_shown"]
    assert spec.props["program"].type is PropType.ENUM
    assert set(spec.props["program"].values) == {"pace", "other"}


# --- access-request intake stub ---------------------------------------------
@pytest.mark.asyncio
async def test_intake_records_the_request_through_the_encrypted_envelope(client: AsyncClient):
    marker = f"Test Patient {uuid.uuid4().hex[:8]}"
    r = await client.post(
        "/v1/access-request",
        json={
            "request_type": "deletion",
            "patient_name": marker,
            "contact": "someone@example.test",
            "relationship": "self",
            "details": "please delete everything",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["received"] is True and body["message"]

    async with AsyncSessionLocal() as s:
        rows = list(
            (
                await s.execute(
                    select(AuditEvent).where(AuditEvent.event_type == "access_request")
                )
            ).scalars()
        )
    payloads = [json.loads(decrypt_payload(bytes(r_.payload_encrypted), r_.key_version)) for r_ in rows]
    mine = [p for p in payloads if p.get("patient_name") == marker]
    assert len(mine) == 1
    assert mine[0]["request_type"] == "deletion"
    assert mine[0]["contact"] == "someone@example.test"
    assert mine[0]["received_at"]


@pytest.mark.asyncio
async def test_intake_is_unauthenticated_and_discloses_nothing(client: AsyncClient):
    """The receipt must be IDENTICAL whether or not the person appears anywhere in Tyndale —
    the response can never become an existence oracle."""
    known = await client.post(
        "/v1/access-request",
        json={"request_type": "access", "patient_name": "Amy Fluegel", "contact": "a@b.test"},
    )
    unknown = await client.post(
        "/v1/access-request",
        json={
            "request_type": "access",
            "patient_name": f"Nobody {uuid.uuid4().hex}",
            "contact": "a@b.test",
        },
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()  # byte-identical receipt


@pytest.mark.asyncio
async def test_intro_surface_explains_the_limits(client: AsyncClient):
    r = await client.get("/v1/access-request")
    assert r.status_code == 200
    assert r.json()["received"] is False
    assert r.json()["message"]


@pytest.mark.asyncio
async def test_bad_request_type_is_rejected(client: AsyncClient):
    r = await client.post(
        "/v1/access-request",
        json={"request_type": "sell_my_data", "patient_name": "X Y", "contact": "a@b.test"},
    )
    assert r.status_code == 422


def test_access_request_event_is_live_with_the_frozen_schema():
    """Flipped LIVE 2026-08-17: migration 0041 made user_id nullable and the emit layer
    allowlists exactly this event for anonymity. The schema is unchanged from its frozen
    registration — flipping live required no churn, which was the point of registering early."""
    spec = REGISTRY["access_request_received"]
    assert spec.not_yet_live is False
    assert set(spec.props["request_type"].values) == {"access", "deletion", "correction"}


# --- the anonymous analytics path (deep review item 5, 2026-08-17) -----------
@pytest.mark.asyncio
async def test_intake_emits_the_anonymous_event_with_a_null_user(client):
    """access_request_received is LIVE: server-side emit at the intake, user_id NULL, the
    request_type enum as the only property — the name/contact/details never leave the
    encrypted audit envelope."""
    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.db.models.analytics_events import AnalyticsEvent

    r = await client.post(
        "/v1/access-request",
        json={"request_type": "deletion", "patient_name": "Jordan Q. Testpatient",
              "contact": "jordan@example.test"},
    )
    assert r.status_code == 200
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(AnalyticsEvent)
                .where(AnalyticsEvent.event_name == "access_request_received")
                .order_by(AnalyticsEvent.occurred_at.desc())
                .limit(1)
            )
        ).scalars().all()
    assert rows, "the intake wrote no analytics event"
    assert rows[0].user_id is None
    assert rows[0].properties == {"request_type": "deletion"}


@pytest.mark.asyncio
async def test_anonymity_is_a_property_of_one_event_not_an_option():
    """Any OTHER event arriving without a user is dropped and counted — the null-user door
    opens for exactly the statutory intake."""
    from app.analytics.emit import ANONYMOUS_EVENTS, emit, get_drop_counts

    assert ANONYMOUS_EVENTS == {"access_request_received"}
    before = get_drop_counts().get("anonymous_not_allowed", 0)
    assert await emit("upload_started", user_id=None, properties={"file_count": 1}) is False
    assert get_drop_counts().get("anonymous_not_allowed", 0) == before + 1
