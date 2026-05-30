"""Phase 2L — multi-document upload tests.

Covers the multi-file request, single-file backwards-compat, attaching all files
to one case (new + existing), per-file + total-request size limits, and the
classifier producing distinct document types. use_real_auth defaults to false,
so uploads run as the seeded dev user; the OCR classify is the keyword stub.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.routes.upload import _classify


@pytest.mark.asyncio
async def test_upload_single_file_backwards_compat(client: AsyncClient):
    content = b"STUB OCR - a hospital bill. Amount Due $100."
    r = await client.post("/v1/upload", files={"file": ("bill.txt", content, "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    uuid.UUID(body["case_file_id"])
    uuid.UUID(body["document_id"])
    assert body["received_bytes"] == len(content)
    assert body["filename"] == "bill.txt"
    assert "uploads" not in body  # legacy single-file shape


@pytest.mark.asyncio
async def test_upload_multiple_files_one_request(client: AsyncClient):
    files = [
        ("files", ("bill.txt", b"Statement Amount Due CPT 70553", "text/plain")),
        ("files", ("eob.txt", b"Explanation of Benefits member responsibility", "text/plain")),
        ("files", ("card.txt", b"Member ID 999 Group Number 1 Rx Bin 4", "text/plain")),
    ]
    r = await client.post("/v1/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "case_file_id" in body
    assert len(body["uploads"]) == 3
    for u in body["uploads"]:
        uuid.UUID(u["document_id"])
        assert u["filename"]
        assert u["size_bytes"] > 0


@pytest.mark.asyncio
async def test_upload_attaches_all_to_one_case_file(client: AsyncClient):
    files = [
        ("files", ("a.txt", b"bill amount due", "text/plain")),
        ("files", ("b.txt", b"explanation of benefits", "text/plain")),
        ("files", ("c.txt", b"member id group number", "text/plain")),
    ]
    r = await client.post("/v1/upload", files=files)
    body = r.json()
    cfid = body["case_file_id"]
    assert len(body["uploads"]) == 3
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))).scalar_one()
    assert len(cf.documents) == 3  # all three on the one case


def test_upload_classifies_each_file_independently():
    # Each document maps to its own type (the route runs _classify per file).
    assert _classify("EXPLANATION OF BENEFITS — member responsibility $50")[0] == "eob"
    assert _classify("Member ID 12345  Group Number 678  Rx Bin 9999")[0] == "insurance_card"
    assert _classify("Hospital STATEMENT — Amount Due $1,200 CPT 70553")[0] == "bill"
    distinct = {
        _classify("EXPLANATION OF BENEFITS")[0],
        _classify("MEMBER ID GROUP NUMBER")[0],
        _classify("AMOUNT DUE STATEMENT")[0],
    }
    assert len(distinct) == 3  # classified differently


@pytest.mark.asyncio
async def test_upload_size_limit_per_file(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_file_bytes", 8)
    r = await client.post(
        "/v1/upload",
        files=[("files", ("big.txt", b"way more than eight bytes", "text/plain"))],
    )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_upload_size_limit_total_request(client: AsyncClient, monkeypatch):
    # Lower the whole-request multipart cap; two files together exceed it.
    monkeypatch.setattr(get_settings(), "max_request_body_bytes", 200)
    big = b"x" * 300
    files = [
        ("files", ("a.txt", big, "text/plain")),
        ("files", ("b.txt", big, "text/plain")),
    ]
    r = await client.post("/v1/upload", files=files)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_upload_to_existing_case_file_appends_documents(client: AsyncClient):
    r1 = await client.post("/v1/upload", files=[("files", ("bill.txt", b"amount due", "text/plain"))])
    assert r1.status_code == 200, r1.text
    cfid = r1.json()["case_file_id"]
    assert len(r1.json()["uploads"]) == 1
    # Attach a second document to the SAME case via case_file_id form field.
    r2 = await client.post(
        "/v1/upload",
        data={"case_file_id": cfid},
        files=[("files", ("eob.txt", b"explanation of benefits", "text/plain"))],
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["case_file_id"] == cfid
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))).scalar_one()
    assert len(cf.documents) == 2  # appended, not replaced
