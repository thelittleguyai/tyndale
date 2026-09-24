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
    content = b"%PDF-1.4 STUB OCR - a hospital bill. Amount Due $100."
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
        ("files", ("bill.txt", b"%PDF-1.4 Statement Amount Due CPT 70553", "text/plain")),
        ("files", ("eob.txt", b"%PDF-1.4 Explanation of Benefits member responsibility", "text/plain")),
        ("files", ("card.txt", b"%PDF-1.4 Member ID 999 Group Number 1 Rx Bin 4", "text/plain")),
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
        ("files", ("a.txt", b"%PDF-1.4 bill amount due", "text/plain")),
        ("files", ("b.txt", b"%PDF-1.4 explanation of benefits", "text/plain")),
        ("files", ("c.txt", b"%PDF-1.4 member id group number", "text/plain")),
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
        files=[("files", ("big.txt", b"%PDF-1.4 way more than eight bytes", "text/plain"))],
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
    r1 = await client.post("/v1/upload", files=[("files", ("bill.txt", b"%PDF-1.4 amount due", "text/plain"))])
    assert r1.status_code == 200, r1.text
    cfid = r1.json()["case_file_id"]
    assert len(r1.json()["uploads"]) == 1
    # Attach a second document to the SAME case via case_file_id form field.
    r2 = await client.post(
        "/v1/upload",
        data={"case_file_id": cfid},
        files=[("files", ("eob.txt", b"%PDF-1.4 explanation of benefits", "text/plain"))],
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["case_file_id"] == cfid
    async with AsyncSessionLocal() as s:
        cf = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(cfid)))).scalar_one()
    assert len(cf.documents) == 2  # appended, not replaced


# ── e2e round 3 R5: a refused file is refused ALONE ─────────────────────────────────────
CORRUPT = ("files", ("corrupt.pdf", b"\x00\x01 this is not a pdf at all", "application/pdf"))
VALID = ("files", ("bill.pdf", b"%PDF-1.4 amount due", "application/pdf"))


@pytest.mark.asyncio
async def test_a_corrupt_file_beside_a_valid_one_is_named_and_nothing_is_stored(client: AsyncClient):
    """The round-3 run: a corrupt PDF sank the valid file beside it, after the files ahead of it
    were already persisted, and the app printed the raw envelope. Now every file is checked
    before any is stored; the answer names each refused file by its place in the request, in
    the registry's voice — the app drops exactly those and sends the rest again."""
    first = await client.post("/v1/upload", files=[VALID])
    cfid = first.json()["case_file_id"]
    async with AsyncSessionLocal() as s:
        before = len((await s.get(CaseFile, uuid.UUID(cfid))).documents)

    r = await client.post("/v1/upload", files=[CORRUPT, VALID], data={"case_file_id": cfid})
    assert r.status_code == 422, r.text
    body = r.json()
    (refused,) = body["rejected"]
    assert refused["index"] == 0 and refused["filename"] == "corrupt.pdf" and refused["code"] == "not_a_document"
    assert refused["reason"].startswith('"corrupt.pdf" isn\'t a PDF or image')
    assert body["detail"] == refused["reason"]  # one line — the only thing the app shows
    async with AsyncSessionLocal() as s:
        assert len((await s.get(CaseFile, uuid.UUID(cfid))).documents) == before  # nothing stored

    again = await client.post("/v1/upload", files=[VALID], data={"case_file_id": cfid})
    assert again.status_code == 200, again.text  # the good file, sent on its own, lands


@pytest.mark.asyncio
async def test_each_refused_file_gets_its_own_reason(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_file_bytes", 32)  # CORRUPT fits; scan.pdf doesn't
    big = ("files", ("scan.pdf", b"%PDF-1.4 " + b"x" * 64, "application/pdf"))
    only_big = await client.post("/v1/upload", files=[big])
    assert only_big.status_code == 413  # every refusal a size one → 413, as before
    assert only_big.json()["rejected"][0]["code"] == "too_large"
    both = await client.post("/v1/upload", files=[big, CORRUPT])
    assert both.status_code == 422
    assert [x["code"] for x in both.json()["rejected"]] == ["too_large", "not_a_document"]
    assert both.json()["detail"].count("\n") == 1  # one line per refused file
