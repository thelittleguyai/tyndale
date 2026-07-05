"""Intake coverage-regime verification ladder (Sprint B, DL-82).

Detection runs off extracted/typed coverage; high-confidence document evidence
auto-verifies, everything else waits for the user's explicit confirm on the
'How are you covered?' step. USE_REAL_AUTH=false, so calls run as the dev user;
each test uses its own fresh case + explicit case_file_id.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.routes.intake import _next_step


async def _dev_user_id() -> uuid.UUID:
    async with AsyncSessionLocal() as s:
        any_case = (await s.execute(select(CaseFile).limit(1))).scalar_one_or_none()
        if any_case is not None:
            return any_case.user_id
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


async def _fresh_case(**fields) -> str:
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid,
            status="open",
            intake_status=fields.pop("intake_status", "in_progress"),
            intake_current_step=fields.pop("intake_current_step", "coverage-regime-confirm"),
            **fields,
        )
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def _state(client: AsyncClient, cfid: str) -> dict:
    return (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()


def test_step_sits_after_insurance_card():
    assert _next_step("insurance-card") == "coverage-regime-confirm"
    assert _next_step("coverage-regime-confirm") == "coverage-details"


async def test_detection_populates_on_manual_entry(client: AsyncClient):
    cfid = await _fresh_case()
    # A Medicaid payer typed in → medium-confidence detection, NOT auto-verified.
    r = await client.post(
        "/v1/intake/step/coverage-details/manual-entry",
        json={"case_file_id": cfid, "payer_name": "MassHealth"},
    )
    assert r.status_code == 200
    cap = (await _state(client, cfid))["captured_data"]
    assert cap["regime_detection"] is not None
    assert cap["regime_detection"]["candidate"] == "medicaid"
    assert cap["regime_detection"]["verified"] is False
    assert cap["coverage_regime"] is None  # medium confidence → the ladder still asks


async def test_high_confidence_document_autoverifies(client: AsyncClient):
    # An MSN on file + an MBI member id is unambiguous → auto-verified, no ask needed.
    cfid = await _fresh_case(documents=[{"document_id": "d1", "document_type": "msn"}])
    await client.post(
        "/v1/intake/step/coverage-details/manual-entry",
        json={"case_file_id": cfid, "member_id": "1EG4TE5MK73"},
    )
    cap = (await _state(client, cfid))["captured_data"]
    assert cap["coverage_regime"] == "medicare_traditional"
    assert cap["regime_detection"]["verified"] is True
    assert cap["regime_detection"]["confidence"] == "high"


async def test_confirm_sets_verified_and_advances(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/step/coverage-regime-confirm/confirm",
        json={"case_file_id": cfid, "coverage_regime": "medicare_advantage"},
    )
    assert r.status_code == 200
    assert r.json()["current_step"] == "coverage-details"  # advanced
    cap = (await _state(client, cfid))["captured_data"]
    assert cap["coverage_regime"] == "medicare_advantage"
    assert cap["regime_detection"]["verified"] is True
    assert cap["regime_detection"]["method"] == "user_declared"


async def test_confirm_rejects_invalid_regime(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/step/coverage-regime-confirm/confirm",
        json={"case_file_id": cfid, "coverage_regime": "medicare"},  # not one of the seven
    )
    assert r.status_code == 422


async def test_user_confirm_is_sticky_against_later_detection(client: AsyncClient):
    cfid = await _fresh_case()
    # User explicitly confirms self_pay.
    await client.post(
        "/v1/intake/step/coverage-regime-confirm/confirm",
        json={"case_file_id": cfid, "coverage_regime": "self_pay"},
    )
    # Later a payer name is typed that would detect commercial — must NOT overwrite.
    await client.post(
        "/v1/intake/step/coverage-details/manual-entry",
        json={"case_file_id": cfid, "payer_name": "Aetna", "group_number": "G1"},
    )
    cap = (await _state(client, cfid))["captured_data"]
    assert cap["coverage_regime"] == "self_pay"
    assert cap["regime_detection"]["verified"] is True


async def test_skip_advances_without_setting_regime(client: AsyncClient):
    cfid = await _fresh_case()
    r = await client.post(
        "/v1/intake/step/coverage-regime-confirm/skip", json={"case_file_id": cfid}
    )
    assert r.status_code == 200
    assert r.json()["current_step"] == "coverage-details"
    cap = (await _state(client, cfid))["captured_data"]
    assert cap["coverage_regime"] is None
