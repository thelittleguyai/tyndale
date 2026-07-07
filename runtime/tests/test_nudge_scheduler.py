"""Nudge scheduler (Sprint G): due-stage selection, bundling, idempotent no-double-send,
gating, and PHI-free copy."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.crons.nudge_cron import (
    NudgeItem,
    _chase_documents,
    _due_stage,
    run_nudge_cron,
    scan_for_nudges,
)
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.findings import Finding

# Coverage with a missing deductible (a USER_CHASE-level chase item) but a payer set.
_CHASE_COVERAGE = {"payer_name": "Aetna", "plan_year": 2026}


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


async def _case_with_old_finding(days_old: int, coverage=None, nudges_sent=None) -> str:
    """A completed case with a chase item + a finding aged ``days_old`` days."""
    uid = await _dev_user_id()
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid,
            status="audit_complete",
            coverage=coverage if coverage is not None else dict(_CHASE_COVERAGE),
            nudges_sent=nudges_sent or [],
        )
        s.add(cf)
        await s.flush()
        s.add(
            Finding(
                finding_id=uuid.uuid4(),
                case_file_id=cf.case_file_id,
                finding_type="payer_side",
                category="cost_sharing_miscalculation",
                subagent_source="math_person",
                voice_tier="B",
                facts={},
                created_at=created,
            )
        )
        await s.commit()
        return str(cf.case_file_id)


def test_due_stage_selection():
    assert _due_stage(2, [], 3, 14) is None  # too early
    assert _due_stage(3, [], 3, 14) == "+3d"
    assert _due_stage(14, [], 3, 14) == "+14d"
    assert _due_stage(14, ["+14d"], 3, 14) is None  # already sent the last stage
    assert _due_stage(20, ["+3d"], 3, 14) == "+14d"  # +3d done, +14d now due
    assert _due_stage(20, ["+3d", "+14d"], 3, 14) is None  # both done → no more sends


def test_chase_documents_are_phi_free_labels():
    docs = _chase_documents({"payer_name": "Aetna"})  # deductible + oop + coinsurance missing
    assert docs == ["your plan's Summary of Benefits (SBC)"]  # deduped, bundled
    # No chase when the load-bearing inputs are present.
    assert _chase_documents({"deductible_amount": 2000, "oop_max_amount": 8000, "coinsurance_percent": 20}) == []


def test_nudge_body_names_documents_never_amounts():
    item = NudgeItem("u", "c", "+3d", ["your plan's Summary of Benefits (SBC)"])
    body = item.body()
    assert "Summary of Benefits" in body
    assert "$" not in body  # never an amount
    assert "Aetna" not in body  # never a payer/provider


@pytest.mark.asyncio
async def test_scan_finds_due_case_bundled():
    cfid = await _case_with_old_finding(15)
    items = await scan_for_nudges()
    mine = [i for i in items if i.case_file_id == cfid]
    assert len(mine) == 1  # one bundled item for the case
    assert mine[0].stage == "+14d"
    assert mine[0].documents == ["your plan's Summary of Benefits (SBC)"]


@pytest.mark.asyncio
async def test_needs_documents_case_is_nudged():
    """HP-1 wiring: a needs_documents audit (status audit_incomplete) with a load-bearing missing
    document is scanned exactly like a completed case — audit_incomplete is a nudge scan status,
    so the honest 'to finish we need…' state feeds the Sprint G scheduler."""
    uid = await _dev_user_id()
    created = datetime.now(timezone.utc) - timedelta(days=15)
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid,
            status="audit_incomplete",
            audit_incomplete_reason="needs_documents",
            coverage=dict(_CHASE_COVERAGE),  # missing cost-share inputs → SBC chase
        )
        s.add(cf)
        await s.flush()
        s.add(
            Finding(
                finding_id=uuid.uuid4(),
                case_file_id=cf.case_file_id,
                finding_type="provider_side",
                category="missing_itemized_bill",
                subagent_source="lead_planner",
                voice_tier="C",
                facts={},
                created_at=created,
            )
        )
        await s.commit()
        cfid = str(cf.case_file_id)

    items = await scan_for_nudges()
    assert any(i.case_file_id == cfid for i in items)  # needs_documents case IS surfaced


@pytest.mark.asyncio
async def test_no_nudge_when_chase_resolved():
    cfid = await _case_with_old_finding(
        15, coverage={"deductible_amount": 2000, "oop_max_amount": 8000, "coinsurance_percent": 20}
    )
    items = await scan_for_nudges()
    assert [i for i in items if i.case_file_id == cfid] == []


@pytest.mark.asyncio
async def test_cron_idempotent_no_double_send(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_nudge_emails", True)
    cfid = await _case_with_old_finding(5)  # due for +3d (5 < 14, so never +14d here)

    async def fake_sender(to, subject, body):
        return True

    # First run sends this case's +3d and records it.
    await run_nudge_cron(sender=fake_sender)
    async with AsyncSessionLocal() as s:
        case = (
            await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))
        ).scalar_one()
        assert "+3d" in (case.nudges_sent or [])

    # The case is no longer due for any stage (its +3d is sent; it isn't +14d-old yet),
    # so a re-scan never picks it again — the idempotency guarantee.
    again = await scan_for_nudges()
    assert cfid not in {i.case_file_id for i in again}


@pytest.mark.asyncio
async def test_cron_gated_off_does_not_send(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_nudge_emails", False)
    await _case_with_old_finding(5)
    sends: list = []

    async def fake_sender(to, subject, body):
        sends.append(to)
        return True

    r = await run_nudge_cron(sender=fake_sender)
    assert r["sent"] == 0
    assert sends == []
