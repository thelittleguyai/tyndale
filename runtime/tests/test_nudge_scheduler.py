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
    item = NudgeItem("u", "c", "+3d", documents=["your plan's Summary of Benefits (SBC)"])
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


# --- the §11.5 check-in nudge (G6, split from the chase 2026-08-17) ----------------------
# Brock's nudge.plus_3d/plus_14d are follow-through copy ("ready to make that first call"),
# not document-chase copy — so they render on the follow-through premise: audit done, a
# gameplan exists, nothing reported yet. The load-bearing assertions: his words verbatim
# (drift-guarded via the registry), the deadline slot never leaks or gets invented, and the
# check-in never fires at a user who already told us how the call went.

_COMPLETE_COVERAGE = {"deductible_amount": 2000, "oop_max_amount": 8000, "coinsurance_percent": 20}


async def _checkin_case(days_old: int, *, actionable=True, last_check=None, nudges_sent=None) -> str:
    """audit_complete, NO chase docs missing, one finding aged `days_old`."""
    uid = await _dev_user_id()
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    async with AsyncSessionLocal() as s:
        cf = CaseFile(
            user_id=uid, status="audit_complete", coverage=dict(_COMPLETE_COVERAGE),
            nudges_sent=nudges_sent or [], last_outcome_check_at=last_check,
        )
        s.add(cf)
        await s.flush()
        s.add(Finding(
            finding_id=uuid.uuid4(), case_file_id=cf.case_file_id,
            finding_type="payer_side", category="cost_sharing_miscalculation",
            subagent_source="math_person", voice_tier="B", facts={},
            recommendation={"action": "Call your insurer to dispute the math."} if actionable else None,
            created_at=created,
        ))
        await s.commit()
        return str(cf.case_file_id)


async def _mine(cfid: str):
    return [i for i in await scan_for_nudges() if i.case_file_id == cfid]


@pytest.mark.asyncio
async def test_checkin_renders_brocks_plus_3d_verbatim():
    from app.agents.context_loader import orchestration_step

    cfid = await _checkin_case(4)
    (item,) = await _mine(cfid)
    assert item.kind == "checkin" and item.stage == "checkin+3d"
    assert item.body() == orchestration_step("nudge.plus_3d")  # his words, not engineering's
    assert "document" not in item.body().lower()  # nothing chase-flavored leaked in


@pytest.mark.asyncio
async def test_checkin_14d_carries_a_persisted_deadline_only():
    from app.db.models.deadlines import Deadline

    cfid = await _checkin_case(15)
    async with AsyncSessionLocal() as s:
        s.add(Deadline(
            case_file_id=uuid.UUID(cfid), deadline_date=(datetime.now(timezone.utc) + timedelta(days=10)).date(),
            deadline_type="payer_response", description="payer response window",
        ))
        await s.commit()
    (item,) = await _mine(cfid)
    assert item.stage == "checkin+14d" and item.deadline_date is not None
    body = item.body()
    assert item.deadline_date in body  # the real date, interpolated
    assert "{deadline_date}" not in body  # never a raw slot


@pytest.mark.asyncio
async def test_checkin_14d_without_a_deadline_degrades_to_the_no_variable_string():
    """His §0 rule 2 applied to email: an unfillable string isn't sent — the nearest honest
    rung (the +3d check-in, which needs no variable) is. Never an invented date, and never
    the in-thread degradation apology, which would be nonsense in an inbox."""
    from app.agents.context_loader import orchestration_step

    cfid = await _checkin_case(15)
    (item,) = await _mine(cfid)
    assert item.stage == "checkin+14d" and item.deadline_date is None
    body = item.body()
    assert body == orchestration_step("nudge.plus_3d")
    assert "{deadline_date}" not in body and "don't have everything" not in body


@pytest.mark.asyncio
async def test_chase_wins_when_both_premises_hold():
    """A blocked audit is the sharper fact — one email per case, and it's the chase."""
    cfid = await _case_with_old_finding(4)  # chase coverage + old finding
    (item,) = await _mine(cfid)
    assert item.kind == "chase"


@pytest.mark.asyncio
async def test_checkin_suppressed_after_the_user_reported_a_call():
    """The call-mode tap stamps last_outcome_check_at; "ready to make that first call?"
    after they told us how it went is tone-deaf, so the check-in stays silent."""
    cfid = await _checkin_case(4, last_check=datetime.now(timezone.utc))
    assert await _mine(cfid) == []


@pytest.mark.asyncio
async def test_checkin_requires_an_actionable_gameplan():
    cfid = await _checkin_case(4, actionable=False)
    assert await _mine(cfid) == []


@pytest.mark.asyncio
async def test_checkin_ledger_is_distinct_from_the_chase_ledger():
    """A case chase-nudged before its documents arrived still gets its check-in after —
    the historical bare "+3d" must not satisfy "checkin+3d"."""
    cfid = await _checkin_case(4, nudges_sent=["+3d"])
    (item,) = await _mine(cfid)
    assert item.stage == "checkin+3d"


def test_checkin_bodies_pass_the_real_phi_guard():
    from app.hooks.pre_tool_use import evaluate_send_email

    for item in (
        NudgeItem("u", "c", "checkin+3d", kind="checkin"),
        NudgeItem("u", "c", "checkin+14d", kind="checkin", deadline_date="2026-09-01"),
    ):
        decision = evaluate_send_email(
            {"to": "member@example.test", "subject": item.subject(), "body": item.body()}
        )
        assert decision.approved, decision.block_reason


def test_checkin_subject_is_not_the_chase_subject():
    assert NudgeItem("u", "c", "checkin+3d", kind="checkin").subject() != NudgeItem("u", "c", "+3d").subject()
