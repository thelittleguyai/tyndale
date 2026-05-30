"""Phase CO-8 — send_email PHI guardrail tests (DL-47).

The guardrail has two surfaces:
  - evaluate_send_email(tool_args): pure decision — allowlisted template OR clean
    deep scan -> approved; PHI patterns -> approved=False with a DL-47 reason.
  - guard_send_email(inp, session): the audited async path — on a PHI block it
    writes a `phi_block` audit_events row and returns approved=False (never raises).

False positives are acceptable (a template is then required); false negatives are
NOT (real PHI must never pass). The decision is content-based and independent of
auth/session state.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.auth.phi_patterns import detect_phi
from app.db.base import AsyncSessionLocal
from app.db.models.audit_events import AuditEvent
from app.hooks.contracts import PreToolUseInput
from app.hooks.pre_tool_use import evaluate_send_email, guard_send_email


# --- pure decision: templates pass ------------------------------------------
def test_magic_link_template_passes():
    r = evaluate_send_email(
        {
            "template_id": "magic_link_signin",
            "subject": "Sign in to Tyndale",
            "body": (
                "Click the link below to sign in. It expires in 15 minutes.\n"
                "https://app.tyndaleapp.net/auth/verify?token=abc123"
            ),
        }
    )
    assert r.approved is True
    assert r.block_reason is None


def test_report_ready_template_passes():
    r = evaluate_send_email(
        {
            "template_id": "report_ready",
            "subject": "Your report is ready",
            "body": "Your report is ready — sign in to see it.",
        }
    )
    assert r.approved is True


# --- pure decision: PHI blocks ----------------------------------------------
def test_phi_dollar_amount_blocked():
    r = evaluate_send_email({"subject": "Update", "body": "Your bill of $1,200 is ready."})
    assert r.approved is False
    assert "DL-47" in (r.block_reason or "")


def test_phi_cpt_code_blocked():
    r = evaluate_send_email({"subject": "Visit", "body": "We reviewed CPT 27447 from your visit."})
    assert r.approved is False


def test_phi_member_id_blocked():
    r = evaluate_send_email({"subject": "Account", "body": "Your member ID is ABCD12345678."})
    assert r.approved is False


def test_phi_diagnosis_word_blocked():
    r = evaluate_send_email({"subject": "Results", "body": "Notes on your diagnosis of diabetes."})
    assert r.approved is False


def test_phi_ssn_blocked():
    r = evaluate_send_email({"subject": "Verify", "body": "SSN on file: 123-45-6789."})
    assert r.approved is False


# --- pure decision: ad-hoc (no template) clean vs PHI -----------------------
def test_unknown_template_with_clean_body_passes():
    body = "Click here to verify your email"
    assert detect_phi(body) == []  # no PHI signal in genuinely clean content
    r = evaluate_send_email({"subject": "Verify your email", "body": body})
    assert r.approved is True


def test_unknown_template_with_phi_blocked():
    r = evaluate_send_email(
        {"subject": "Balance", "body": "You owe $450 on your account; amount due now."}
    )
    assert r.approved is False


# --- audited async path: a block writes a phi_block audit row ---------------
@pytest.mark.asyncio
async def test_audit_event_written_on_block():
    case_id = uuid.uuid4()
    inp = PreToolUseInput(
        case_file_id=str(case_id),
        actor="lead_planner",
        tool_name="send_email",
        tool_args={"subject": "Your bill", "body": "Your bill of $1,200 is ready."},
    )
    async with AsyncSessionLocal() as s:
        result = await guard_send_email(inp, s)
        await s.commit()

    # (d) PHI detection returns approved=False — not a raised 500.
    assert result.approved is False
    assert "DL-47" in (result.block_reason or "")

    # (c) exactly one phi_block row written for this case.
    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(AuditEvent).where(AuditEvent.case_file_id == case_id)))
            .scalars()
            .all()
        )
    phi_rows = [r for r in rows if r.event_type == "phi_block"]
    assert len(phi_rows) == 1
    assert phi_rows[0].outcome == "blocked"
    assert phi_rows[0].tools_invoked == ["send_email"]


@pytest.mark.asyncio
async def test_guard_allowlisted_template_passes_and_writes_no_audit():
    """An allowlisted template is approved by the audited path and writes NO row."""
    case_id = uuid.uuid4()
    inp = PreToolUseInput(
        case_file_id=str(case_id),
        actor="lead_planner",
        tool_name="send_email",
        tool_args={"template_id": "magic_link_signin", "subject": "Sign in", "body": "link"},
    )
    async with AsyncSessionLocal() as s:
        result = await guard_send_email(inp, s)
        await s.commit()
    assert result.approved is True

    async with AsyncSessionLocal() as s:
        rows = (
            (await s.execute(select(AuditEvent).where(AuditEvent.case_file_id == case_id)))
            .scalars()
            .all()
        )
    assert rows == []
