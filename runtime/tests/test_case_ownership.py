"""Regression tests for the audit/encounter IDOR fix.

The /v1/audit family previously took any case_file_id with no auth — any
caller who knew/guessed a UUID could run audits and read line items for
another user's case. Every route must now 404 on cases the current user
doesn't own (404, not 403 — anti-enumeration, matching upload.py).

Under dev auth the client resolves to the seeded dev user, so a case owned
by a different user exercises the not-owned branch.
"""

from __future__ import annotations

import uuid

from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.users import User


async def _other_users_case() -> str:
    """Create a case owned by a freshly minted non-dev user."""
    async with AsyncSessionLocal() as s:
        other = User(email=f"other-{uuid.uuid4().hex[:12]}@example.com")
        s.add(other)
        await s.flush()
        cf = CaseFile(user_id=other.user_id, status="open")
        s.add(cf)
        await s.commit()
        return str(cf.case_file_id)


async def test_audit_routes_404_on_not_owned_case(client):
    case_id = await _other_users_case()

    r = await client.post("/v1/audit", json={"case_file_id": case_id})
    assert r.status_code == 404, r.text

    r = await client.get(f"/v1/audit/{case_id}")
    assert r.status_code == 404, r.text

    r = await client.post(f"/v1/audit/{case_id}/extract")
    assert r.status_code == 404, r.text

    r = await client.get(f"/v1/audit/{case_id}/line-items")
    assert r.status_code == 404, r.text

    r = await client.post(
        f"/v1/audit/{case_id}/confirmations",
        json={"confirmations": [{"line_item_id": "li_1", "response": "yes"}]},
    )
    assert r.status_code == 404, r.text

    r = await client.get(f"/v1/audit/{case_id}/status")
    assert r.status_code == 404, r.text


async def test_audit_routes_404_on_unknown_case(client):
    ghost = str(uuid.uuid4())
    for path, method in [
        (f"/v1/audit/{ghost}", "get"),
        (f"/v1/audit/{ghost}/line-items", "get"),
        (f"/v1/audit/{ghost}/status", "get"),
    ]:
        r = await getattr(client, method)(path)
        assert r.status_code == 404, f"{path}: {r.status_code} {r.text}"


async def test_audit_still_400_on_non_uuid(client):
    r = await client.post("/v1/audit", json={"case_file_id": "not-a-uuid"})
    assert r.status_code == 400
