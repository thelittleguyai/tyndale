"""Attest-and-proceed (Brock §A2 state 1) — the compliance state.

The load-bearing assertions: the fuzzy trigger fires on a real name mismatch and NEVER on
missing data; encounter verification is gated until attested; the decline closes the case
gracefully with no audit; and BOTH directions persist an `attestation` audit row through the
ENCRYPTED envelope (the compliance point) while analytics stays PHI-free.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.agents.attest import (
    RELATIONSHIPS,
    attest_edge_signals,
    derive_patient_name,
    evaluate_attest_state,
    names_match,
)
from app.analytics.events import REGISTRY, PropType
from app.db.base import AsyncSessionLocal
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.security.audit_crypto import decrypt_payload


# --- fuzzy matching: the worked example + the never-fabricate rule -----------
@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("AMY E FLUEGEL", "Amy Fluegel", True),  # Brock's worked example
        ("amy fluegel", "AMY FLUEGEL", True),
        ("Amy E. Fluegel", "Amy Fluegel", True),
        ("Fluegel, Amy", "Amy Fluegel", True),  # token-order noise
        ("Amy Fluegel", "Robert Fluegel", False),  # real mismatch → attest
        ("Amy Fluegel", "Amy Chen", False),
        (None, "Amy Fluegel", None),  # unknowable — never a mismatch
        ("Amy Fluegel", None, None),
        ("", "  ", None),
        ("A B", "Amy Fluegel", None),  # single-letter tokens are noise, not a name
    ],
)
def test_names_match_fuzzy_and_never_fabricates(a, b, expected):
    assert names_match(a, b) is expected


class _Case:
    def __init__(self, **kw):
        self.documents = kw.get("documents", [])
        self.patient_name = kw.get("patient_name")
        self.attest_status = kw.get("attest_status", "not_required")


class _User:
    def __init__(self, first, last):
        self.first_name, self.last_name = first, last


def test_trigger_flips_required_only_on_a_real_mismatch():
    mismatch = _Case(patient_name="Robert Fluegel")
    assert evaluate_attest_state(mismatch, _User("Amy", "Fluegel")) is True
    assert mismatch.attest_status == "required"

    ok = _Case(patient_name="AMY E FLUEGEL")
    assert evaluate_attest_state(ok, _User("Amy", "Fluegel")) is False
    assert ok.attest_status == "not_required"

    unknown = _Case()  # no extracted patient name anywhere
    assert evaluate_attest_state(unknown, _User("Amy", "Fluegel")) is False


def test_backfill_guard_evaluates_pre_migration_cases_from_documents():
    """Amy's Beloit case shape: no typed patient_name column value, but the OCR preview has one.
    It must be derived + evaluated on next open — never silently grandfathered."""
    case = _Case(documents=[{"ocr_text_preview": "PATIENT NAME: Robert Fluegel\nDOS 03/14/2026"}])
    assert derive_patient_name(case) == "Robert Fluegel"
    assert evaluate_attest_state(case, _User("Amy", "Fluegel")) is True
    assert case.attest_status == "required"
    assert case.patient_name == "Robert Fluegel"  # typed field persisted (DL-39)


def test_settled_attestations_are_never_re_prompted():
    for settled in ("attested", "declined"):
        case = _Case(patient_name="Robert Fluegel", attest_status=settled)
        assert evaluate_attest_state(case, _User("Amy", "Fluegel")) is False
        assert case.attest_status == settled


def test_edge_signals_are_prompts_from_typed_fields_only():
    teen = _Case(documents=[{"patient_dob": "2011-05-02"}])
    assert "teen" in attest_edge_signals(teen)
    adult = _Case(documents=[{"patient_dob": "1980-05-02"}])
    assert attest_edge_signals(adult) == []
    assert "deceased" in attest_edge_signals(_Case(), patient_deceased=True)
    assert "substance" in attest_edge_signals(_Case(documents=[{"program_type": "substance_use"}]))
    assert attest_edge_signals(_Case(documents=[{"patient_dob": "not-a-date"}])) == []  # no guess


# --- the compliance record (DB) ---------------------------------------------
async def _case_needing_attest(client: AsyncClient) -> tuple[str, uuid.UUID]:
    """A case owned by the authed user whose extracted patient name mismatches their profile.
    Uses the dev auth stub's stable identity (not an analytics round-trip, which can rate-limit)."""
    from app.auth.dev_user import DEV_USER_ID, _ensure_dev_user_row

    async with AsyncSessionLocal() as s:
        await _ensure_dev_user_row(s)  # direct seed — no HTTP call (the dashboard hits Claude)
        uid = DEV_USER_ID
        me = (await s.execute(select(User).where(User.user_id == uid))).scalar_one()
        me.first_name, me.last_name = "Amy", "Fluegel"
        case = CaseFile(
            user_id=uid,
            status="encounter_verification_pending",
            patient_name="Robert Fluegel",
            attest_status="required",
        )
        s.add(case)
        await s.commit()
        return str(case.case_file_id), uid


async def _attestation_rows(case_id: str) -> list[AuditEvent]:
    async with AsyncSessionLocal() as s:
        return list(
            (
                await s.execute(
                    select(AuditEvent)
                    .where(AuditEvent.case_file_id == uuid.UUID(case_id))
                    .where(AuditEvent.event_type == "attestation")
                )
            ).scalars()
        )


@pytest.mark.asyncio
async def test_encounter_verification_is_gated_until_attested(client: AsyncClient):
    """Both closed directions of the gate. (Deliberately does NOT post confirmations after
    attesting — that kicks the real finalize_audit background task; the state transition is
    the thing under test, and the open path is covered by the harness scenario.)"""
    case_id, _ = await _case_needing_attest(client)
    payload = {"confirmations": [{"line_item_id": "li-1", "response": "yes"}]}

    blocked = await client.post(f"/v1/audit/{case_id}/confirmations", json=payload)
    assert blocked.status_code == 409, blocked.text  # attestation outstanding

    ok = await client.post(f"/v1/case/{case_id}/attest", json={"relationship": "spouse_partner"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["attest_status"] == "attested"
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert case.attest_status == "attested"  # gate released

    declined_id, _ = await _case_needing_attest(client)
    await client.post(f"/v1/case/{declined_id}/attest/decline")
    after_decline = await client.post(f"/v1/audit/{declined_id}/confirmations", json=payload)
    assert after_decline.status_code == 409, after_decline.text  # closed case stays closed


@pytest.mark.asyncio
async def test_attestation_persists_through_the_encrypted_envelope(client: AsyncClient):
    """The compliance point: relationship + timestamp + user + case + patient-name-AS-EXTRACTED,
    written through build_audit_event (so it inherits AES-GCM whenever a key is configured)."""
    case_id, uid = await _case_needing_attest(client)
    r = await client.post(f"/v1/case/{case_id}/attest", json={"relationship": "adult_child_caregiver"})
    assert r.status_code == 200

    rows = await _attestation_rows(case_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == uid and row.actor == str(uid)
    payload = decrypt_payload(bytes(row.payload_encrypted), row.key_version)
    import json

    body = json.loads(payload)
    assert body["action"] == "attested"
    assert body["relationship"] == "adult_child_caregiver"
    assert body["patient_name_as_extracted"] == "Robert Fluegel"
    assert body["attested_at"]


@pytest.mark.asyncio
async def test_decline_closes_the_case_gracefully_and_is_also_logged(client: AsyncClient):
    case_id, _ = await _case_needing_attest(client)
    r = await client.post(f"/v1/case/{case_id}/attest/decline")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attest_status"] == "declined"
    assert body["case_status"] == "attest_declined"
    assert body["confirmation"]  # an honest message, never empty

    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_id)))
        ).scalar_one()
        assert case.status == "attest_declined" and case.attest_status == "declined"

    rows = await _attestation_rows(case_id)
    import json

    assert [json.loads(decrypt_payload(bytes(r_.payload_encrypted), r_.key_version))["action"]
            for r_ in rows] == ["declined"]

    # No audit runs after a decline, and the flow can't be resumed by attesting later.
    late = await client.post(f"/v1/case/{case_id}/attest", json={"relationship": "other"})
    assert late.status_code == 409


@pytest.mark.asyncio
async def test_bad_relationship_is_rejected(client: AsyncClient):
    case_id, _ = await _case_needing_attest(client)
    r = await client.post(f"/v1/case/{case_id}/attest", json={"relationship": "nosy_neighbor"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_attest_route_enforces_case_ownership(client: AsyncClient):
    async with AsyncSessionLocal() as s:
        other = User(email=f"other-{uuid.uuid4().hex[:10]}@example.test")
        s.add(other)
        await s.flush()
        theirs = CaseFile(user_id=other.user_id, status="encounter_verification_pending",
                          attest_status="required")
        s.add(theirs)
        await s.commit()
        their_id = str(theirs.case_file_id)

    r = await client.post(f"/v1/case/{their_id}/attest", json={"relationship": "other"})
    assert r.status_code == 404  # anti-enumeration, same as every case route


@pytest.mark.asyncio
async def test_analytics_stay_phi_free(client: AsyncClient):
    """The relationship enum is recorded; the patient NAME never leaves the audit envelope."""
    for name in ("attestation_required", "attestation_recorded", "attestation_declined"):
        for pspec in REGISTRY[name].props.values():
            # Only enum/number/boolean exist — a free-text (name-carrying) prop is structurally
            # impossible, which is what keeps the patient name out of analytics.
            assert pspec.type in (PropType.ENUM, PropType.NUMBER, PropType.BOOLEAN)
    assert set(REGISTRY["attestation_recorded"].props) == {"relationship"}
    assert set(REGISTRY["attestation_recorded"].props["relationship"].values) == set(RELATIONSHIPS)

    case_id, _ = await _case_needing_attest(client)
    await client.post(f"/v1/case/{case_id}/attest", json={"relationship": "executor"})
    async with AsyncSessionLocal() as s:
        rows = list(
            (
                await s.execute(
                    select(AnalyticsEvent).where(
                        AnalyticsEvent.case_file_id == uuid.UUID(case_id)
                    )
                )
            ).scalars()
        )
    assert rows, "attestation must emit its analytics event"
    assert all("Fluegel" not in str(r.properties) for r in rows)


@pytest.mark.asyncio
async def test_declined_case_count_is_isolated(client: AsyncClient):
    """A decline must not leave the case in any open/auditable state."""
    case_id, _ = await _case_needing_attest(client)
    await client.post(f"/v1/case/{case_id}/attest/decline")
    async with AsyncSessionLocal() as s:
        open_like = (
            await s.execute(
                select(func.count())
                .select_from(CaseFile)
                .where(CaseFile.case_file_id == uuid.UUID(case_id))
                .where(CaseFile.status.in_(["audit_running", "encounter_verification_pending"]))
            )
        ).scalar_one()
    assert open_like == 0
