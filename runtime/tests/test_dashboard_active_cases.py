"""Dashboard status-aware Open Cases card (Item 1, 2026-07-06).

A user with an in-flight or completed audit previously saw nothing on the dashboard — the
resume card only existed for interrupted intake. active_cases makes every non-terminal case
resumable with a plain-language status and the screen that resumes it (pre-audit -> encounter,
audit lifecycle -> results). Terminal cases (resolved/archived) never appear."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile


async def _dev_uid() -> uuid.UUID:
    from app.auth.dev_user import resolve_dev_user

    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        await s.commit()
        return u.user_id


@pytest.mark.asyncio
async def test_active_cases_are_status_aware_and_resumable(client: AsyncClient):
    uid = await _dev_uid()
    expected = {
        "encounter_verification_pending": ("Verify your visit", "encounter"),
        "audit_running": ("Audit running", "results"),
        "audit_complete": ("Results ready", "results"),
        "audit_incomplete": ("Audit incomplete", "results"),
        "extraction_failed": ("We couldn't read your documents", "encounter"),
    }
    ids: dict[str, str] = {}
    async with AsyncSessionLocal() as s:
        for st in expected:
            cf = CaseFile(user_id=uid, status=st, intake_status="complete")
            s.add(cf)
            await s.flush()
            ids[st] = str(cf.case_file_id)
        # A terminal case must NOT surface as a resumable card.
        resolved = CaseFile(user_id=uid, status="resolved", intake_status="complete")
        s.add(resolved)
        await s.flush()
        resolved_id = str(resolved.case_file_id)
        await s.commit()

    body = (await client.get("/v1/dashboard")).json()
    by_id = {c["case_file_id"]: c for c in body["active_cases"]}

    for st, (label, resume) in expected.items():
        card = by_id.get(ids[st])
        assert card is not None, f"{st} case missing from active_cases"
        assert card["status"] == st
        assert card["label"] == label
        assert card["resume"] == resume  # pre-audit -> encounter; audit lifecycle -> results

    assert resolved_id not in by_id  # terminal cases are not resumable cards
