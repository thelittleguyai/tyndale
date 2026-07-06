"""Intake re-gating regression (2026-07-06). A user who completed intake on an older case
must never be re-gated into the wizard when a newer case appears — a fresh upload creates a
case with intake_status='not_started', and the old most-recent-case derivation flipped the
gate to incomplete, trapping returning users. Intake is a one-time, user-level state."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from httpx import AsyncClient
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.routes.dashboard import _intake_state


def _c(status: str, step: str | None = None, days_ago: int = 0):
    return SimpleNamespace(
        intake_status=status,
        intake_current_step=step,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


# --- pure derivation (the exact regression) ---
def test_completed_intake_is_not_regated_by_a_newer_case():
    completed = _c("complete", "complete", days_ago=10)
    fresh_upload = _c("not_started", None, days_ago=0)  # most recent
    assert _intake_state([completed, fresh_upload]) == ("complete", "complete")
    assert _intake_state([fresh_upload, completed]) == ("complete", "complete")  # order-independent


def test_brand_new_user_is_routed_to_the_wizard():
    assert _intake_state([]) == ("not_started", "welcome")
    assert _intake_state([_c("not_started")]) == ("not_started", "welcome")


def test_in_progress_resumes_step_when_no_completed_case_exists():
    assert _intake_state([_c("in_progress", "deductible")]) == ("in_progress", "deductible")


# --- dashboard route + audit-endpoint independence ---
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


async def test_dashboard_stays_complete_after_a_fresh_upload_case(client: AsyncClient):
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        s.add(
            CaseFile(
                user_id=uid, status="audit_complete",
                intake_status="complete", intake_current_step="complete",
            )
        )
        # A newer, upload-created case defaults to not_started (the trap trigger).
        s.add(CaseFile(user_id=uid, status="open", intake_status="not_started"))
        await s.commit()

    body = (await client.get("/v1/dashboard")).json()
    assert body["intake_status"] == "complete"  # NOT flipped by the newer not_started case
    assert body["has_cases"] is True


async def test_audit_endpoint_unaffected_by_intake_state(client: AsyncClient):
    """A running/complete audit must be reachable regardless of intake — the audit routes
    don't consult intake state, so a not_started case still serves its audit."""
    uid = await _dev_user_id()
    async with AsyncSessionLocal() as s:
        cf = CaseFile(user_id=uid, status="audit_running", intake_status="not_started")
        s.add(cf)
        await s.commit()
        cfid = str(cf.case_file_id)

    r = await client.get(f"/v1/audit/{cfid}")
    assert r.status_code == 200  # served, not gated on intake
