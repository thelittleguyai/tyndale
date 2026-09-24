"""POST /v1/upload — multi-document upload (Phase 2L).

Accepts N files in one multipart request (bill + EOB + insurance card + plan
summary, per the acceptance narrative "Maya uploads four crumpled photos"),
persists + classifies each, and attaches them all to one case file — a new case,
or an existing one via case_file_id.

Backwards compat (14-day window per the phase prompt): the old singular shape
(file=...) is still accepted and returns the legacy single-file response; a
deprecation warning is logged.

Storage / classification stay the walking-skeleton approach (Azure Blob or local
/tmp; keyword OCR classify with a heuristic confidence). Per-file + total request
size are bounded by Phase 2K.2 (per-file here, total request in the size-limit
middleware).
"""

from __future__ import annotations

import base64
import datetime
import re
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.attest import evaluate_attest_state
from app.agents.context_loader import orchestration_step
from app.agents.orchestrator import documents_all_satisfied, finalize_audit, reread_for_new_document
from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.db.session import get_session
from app.intake.planner import BILL_TYPES
from app.schemas.api_contract import MultiUploadResponse, UploadedDoc, UploadResponse
from app.sources.call_identifiers import derive_call_identifiers
from app.sources.document_classifier import classify_document
from app.sources.extraction import (  # OCR engine (CO-12A: moved out of ocr_tools)
    _grep_date,
    grep_account_number,
    grep_claim_number,
    grep_contact_phone,
    grep_patient_name,
    grep_patient_state,
    grep_provider_name,
    run_document_ocr,
)

router = APIRouter(tags=["v1"])
log = structlog.get_logger(__name__)


# The benefits document goes by a dozen names — recognize them ALL as the
# plan_summary type (CO-12C). Human-readable list (surfaced to the UI) + the
# uppercase match markers. Acronyms are matched parenthesized "(SBC)" to avoid
# false-positiving a bare "SBC"/"EOC" substring inside a bill.
BENEFITS_DOC_ALIASES: tuple[str, ...] = (
    "Summary of Benefits and Coverage (SBC)",
    "Schedule of Benefits",
    "Summary Plan Description (SPD)",
    "Benefit Summary / Plan Summary",
    "Certificate of Coverage (COC)",
    "Evidence of Coverage (EOC)",
    "Outline of Coverage",
    "Member Benefit Booklet / Benefit Booklet / Member Handbook",
    "Plan Document",
    "Coverage Summary",
    "Benefits at a Glance",
)
def _classify(ocr_text: str, filename: str | None = None) -> tuple[str, float]:
    """Return (document_type, classification_confidence) via the layered classifier
    (Sprint E). Adds MSN / MA-EOB / Medicaid-MCO / GFE / TRICARE / VA / community-care
    types; an ambiguous document is 'unclassified', never guessed."""
    return classify_document(ocr_text, filename).as_tuple()


def _safe_storage_name(filename: str | None) -> str:
    """The filename component of a blob/disk STORAGE name (LOW hygiene, 2026-08-19 review).
    Path separators and dot-dot sequences are stripped defensively — the uuid prefix
    already neutralizes traversal, but a storage name should never carry client-controlled
    path structure at all. Display keeps the original filename; only storage names change."""
    safe = re.sub(r"[/\\]+", "_", filename or "upload")
    safe = safe.replace("..", "_")
    return safe[-100:] or "upload"


async def _persist(content: bytes, filename: str) -> str:
    """Write the upload to local disk or Azure Blob; return a URI/path string."""
    settings = get_settings()
    if settings.azure_storage_account_url:
        try:
            # Async client → async credential (the sync DefaultAzureCredential is not
            # awaitable and breaks the aio client). Both are async context managers, so
            # `async with` closes the credential's aiohttp session + the client cleanly.
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            async with DefaultAzureCredential() as cred, BlobServiceClient(
                account_url=settings.azure_storage_account_url, credential=cred
            ) as svc:
                container = svc.get_container_client(settings.azure_storage_uploads_container)
                blob_name = f"{uuid.uuid4()}_{_safe_storage_name(filename)}"
                await container.upload_blob(name=blob_name, data=content, overwrite=False)
                return f"{settings.azure_storage_account_url}/{settings.azure_storage_uploads_container}/{blob_name}"
        except Exception as exc:  # noqa: BLE001 — Blob is the durable store; never downgrade
            # PHI must land durably in Azure Blob (BAA-covered, DL-47). Never silently fall
            # back to the replica's EPHEMERAL local disk when Blob is the configured store —
            # that loses PHI on restart and puts it on non-durable, off-BAA storage. Fail clean.
            log.error(
                "upload.blob_failed",
                error_class=type(exc).__name__,
                container=settings.azure_storage_uploads_container,
                exc_info=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Upload storage is temporarily unavailable — please try again in a moment.",
            ) from exc

    # No Azure Blob configured → local disk. Acceptable ONLY in local dev; NEVER in
    # production (an ephemeral upload store in prod means PHI loss + off-BAA storage).
    if settings.is_production:
        log.error("upload.no_durable_storage_in_prod")
        raise HTTPException(
            status_code=503,
            detail="Upload storage is not available — please try again later.",
        )
    target_dir = Path(settings.local_uploads_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{_safe_storage_name(filename)}"
    path = target_dir / safe_name
    path.write_bytes(content)
    return str(path)


_MIME_BY_SNIFF = {
    "pdf": "application/pdf", "jpeg": "image/jpeg", "png": "image/png",
    "tiff": "image/tiff", "bmp": "image/bmp", "heic": "image/heic",
}  # fmt: skip


def stored_media_type(content: bytes) -> str:
    """The content-type to serve a stored upload with — from its MAGIC BYTES (the same sniff
    that admitted it), never from the user-supplied filename."""
    return _MIME_BY_SNIFF.get(_sniff_upload_type(content) or "", "application/octet-stream")


async def read_stored(uri: str | None) -> bytes | None:
    """Read ONE stored upload back (the reviewer's document viewer). Like delete_stored it only
    ever touches our own store — a blob under the configured account + uploads container, or a
    file inside local_uploads_dir; any other URI (whatever a document entry claims) returns None.
    Reads only: nothing is copied, cached or written."""
    if not uri:
        return None
    settings = get_settings()
    if settings.azure_storage_account_url:
        prefix = f"{settings.azure_storage_account_url}/{settings.azure_storage_uploads_container}/"
        if not uri.startswith(prefix):
            return None
        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            async with DefaultAzureCredential() as cred, BlobServiceClient(
                account_url=settings.azure_storage_account_url, credential=cred
            ) as svc:
                container = svc.get_container_client(settings.azure_storage_uploads_container)
                stream = await container.download_blob(uri[len(prefix):])
                return await stream.readall()
        except Exception as exc:  # noqa: BLE001 — the viewer says "unavailable", never 500s
            log.warning("upload.read_stored_failed", error_class=type(exc).__name__)
            return None
    try:
        root = Path(settings.local_uploads_dir).resolve()
        target = Path(uri).resolve()
        if root in target.parents and target.is_file():
            return target.read_bytes()
    except OSError as exc:
        log.warning("upload.read_stored_failed", error_class=type(exc).__name__)
    return None


async def delete_stored(uri: str | None) -> bool:
    """Best-effort removal of ONE stored upload — the e2e teardown's counterpart to _persist.
    Only ever touches our own store: a blob under the configured account + uploads container, or
    a file inside local_uploads_dir. Anything else is left alone and reported False."""
    if not uri:
        return False
    settings = get_settings()
    if settings.azure_storage_account_url:
        prefix = f"{settings.azure_storage_account_url}/{settings.azure_storage_uploads_container}/"
        if not uri.startswith(prefix):
            return False
        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            async with DefaultAzureCredential() as cred, BlobServiceClient(
                account_url=settings.azure_storage_account_url, credential=cred
            ) as svc:
                container = svc.get_container_client(settings.azure_storage_uploads_container)
                await container.delete_blob(uri[len(prefix):])
            return True
        except Exception as exc:  # noqa: BLE001 — teardown is best-effort about bytes
            log.warning("upload.delete_stored_failed", error_class=type(exc).__name__)
            return False
    try:
        root = Path(settings.local_uploads_dir).resolve()
        target = Path(uri).resolve()
        if root in target.parents and target.is_file():
            target.unlink()
            return True
    except OSError as exc:
        log.warning("upload.delete_stored_failed", error_class=type(exc).__name__)
    return False


# HEIC/HEIF ISO-BMFF brands (bytes 8-12) we accept — iPhone photos are 'heic'/'mif1'.
_HEIF_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"heif"}
)


def _sniff_upload_type(content: bytes) -> str | None:
    """Content-based (magic-byte) file type — the ONLY trustworthy signal (the client MIME/
    extension is user-controlled). Returns a short type name for a PDF or an Azure-DI-processable
    image, else None. Closes the security gap where any ≤20MB payload was stored + sent to OCR,
    and lets a non-document upload fail fast at the door with a readable 422 instead of dead-ending
    on a 0-item encounter screen."""
    if not content:
        return None
    if content[:4] == b"%PDF":
        return "pdf"
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if content[:2] == b"BM":
        return "bmp"
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in _HEIF_BRANDS:
        return "heic"
    return None


# The checklist keys an expectation can name → the classifier families that satisfy it
# (mirrors orchestrator's family sets; the checklist's have-flags use the same grouping).
_EXPECTED_FAMILIES: dict[str, set[str]] = {
    "eob": {"eob", "ma_eob", "msn", "tricare_eob"},
    "itemized_bill": {"bill", "gfe", "itemized_bill"},
    "sbc": {"plan_summary", "insurance_card"},
}


def _rejection(index: int, filename: str, content: bytes) -> dict[str, Any] | None:
    """Why one file cannot be taken — in the registry's voice, naming the file — or None."""
    if len(content) > get_settings().max_upload_file_bytes:
        code, key = "too_large", "upload_rejected_too_large"
    elif _sniff_upload_type(content) is None:
        code, key = "not_a_document", "upload_rejected_not_document"
    else:
        return None
    return {"index": index, "filename": filename, "code": code,
            "reason": orchestration_step(key, filename=filename)}


async def _process_one(content: bytes, filename: str) -> tuple[dict[str, Any], UploadedDoc]:
    """Persist + classify one file. Returns (case-file document entry, API doc)."""
    settings = get_settings()
    if len(content) > settings.max_upload_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"'{filename}' exceeds the {settings.max_upload_file_bytes}-byte per-file limit. "
                "Upload a smaller file — V1-Lite does not support chunked upload."
            ),
        )
    # Reject non-PDF/non-image payloads BEFORE storing or OCRing them (security + honesty): a
    # grocery-list .txt, a Word doc, an empty file, etc. can never become a bill, so fail fast with
    # a readable reason instead of persisting arbitrary bytes and dead-ending on a 0-item encounter.
    if _sniff_upload_type(content) is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{filename}' doesn't look like a PDF or image. Upload a PDF, or a clear photo "
                "(JPG, PNG, or HEIC) of your bill, EOB, insurance card, or plan summary."
            ),
        )
    uri = await _persist(content, filename)
    ocr = await run_document_ocr(
        {"content_base64": base64.b64encode(content).decode(), "filename": filename}
    )
    full_text = ocr.get("ocr_text") or ""
    document_type, confidence = _classify(full_text, filename)
    document_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "document_id": document_id,
        "filename": filename,
        "uri": uri,
        "document_type": document_type,
        "classification_confidence": confidence,
        # Typed extraction at parse time (DL-39) — the Record row title/date read these, never
        # parsed-back-out-of prose. Conservative; None when no structured anchor is present.
        "provider_name": grep_provider_name(full_text),
        "patient_name": grep_patient_name(full_text),
        # Suggestion-grade patient-address state (2026-08-19): prefills the profile field
        # as a CONFIRMED suggestion, never a silent write.
        "patient_state": grep_patient_state(full_text),
        "date_of_service": _grep_date(full_text, ("DATE OF SERVICE", "SERVICE DATE", "DOS")),
        # Call identifiers (B4). Extracted per DOCUMENT because that's where they're true — a
        # case with three EOBs has three claim numbers. `contact_phone` is stored party-neutral
        # here; whose number it is follows from this entry's document_type at promotion time.
        "claim_number": grep_claim_number(full_text),
        "account_number": grep_account_number(full_text),
        "contact_phone": grep_contact_phone(full_text),
        "byte_count": len(content),
        # Full OCR text (already capped at 50k by run_document_ocr): the haystack for the
        # translate-grounding guard — a line item whose code appears in NO document's text is
        # prompt-example bleed, not the user's bill (first caught: dev sweep 2026-08-17, a
        # photographed bill whose thin OCR let the agent echo the skill's 70553 example).
        "ocr_text": full_text[:50000],
        "ocr_text_preview": (ocr.get("ocr_text") or "")[:1000],
        # Full OCR text length (admin visibility): 0 chars alongside extraction_status='error'
        # is the tell that extraction degraded — so a stalled/degraded audit is diagnosable.
        "ocr_text_chars": len(ocr.get("ocr_text") or ""),
        # 'extracted' | 'error' — a real-OCR failure degrades here (empty text) instead of
        # crashing the request; the document is still persisted so nothing is lost.
        "extraction_status": ocr.get("extraction_status") or "extracted",
    }
    if document_type in _EXPECTED_FAMILIES["eob"]:
        # The EOB timeline's data model (doc 40 §A7): WHOSE statement this is — a family plan's
        # deductible accumulates across every covered member — and which accumulator it fed.
        # Both are nullable: set only when the document itself says so. `source` is the typed
        # TimelineSource seam (upload | api); only upload exists today (forwarding dropped,
        # decision 6).
        from app.sources.extraction import _network_status

        entry["member"] = entry["patient_name"]
        entry["network"] = _network_status(full_text)
        entry["source"] = "upload"
    api_doc = UploadedDoc(
        document_id=document_id,
        filename=filename,
        document_type=document_type,
        classification_confidence=confidence,
        size_bytes=len(content),
    )
    return entry, api_doc


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    request: Request,
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(default=None),  # deprecated singular form (14-day compat)
    case_file_id: str | None = Form(default=None),
    # Checklist per-item Add (Brock image-3, 2026-08-22): the client names the document TYPE
    # it expects this upload to satisfy (eob | itemized_bill | sbc) so the classifier's
    # verdict can be compared against the user's intent — a mismatch is measured (analytics)
    # rather than silently absorbed. Optional; plain uploads carry no expectation.
    expected_type: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
):
    # Backwards compat: the old single-file shape (file=...). Returns the legacy
    # response so in-flight clients don't break.
    singular = file is not None and not files
    incoming = [file] if singular else list(files)
    if not incoming:
        raise HTTPException(status_code=400, detail="no files provided")
    if singular:
        log.warning("upload.deprecated_singular_file_form", note="use files=[...] (Phase 2L)")

    # Attach to an existing case, or open a new one.
    case: CaseFile | None = None
    if case_file_id:
        try:
            cf_uuid = UUID(case_file_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="case_file_id must be a UUID") from None
        case = (
            await session.execute(select(CaseFile).where(CaseFile.case_file_id == cf_uuid))
        ).scalar_one_or_none()
        # 404 covers both not-found and not-owned (anti-enumeration).
        if case is None or case.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="case_file not found")

    # Every file is checked BEFORE any is stored (e2e round 3 R5): one bad file used to fail the
    # request midway — after the files ahead of it were already persisted — and the app printed
    # the raw envelope. Now the answer names each refused file, in the registry's voice, nothing
    # is stored, and the app drops exactly those and keeps the good ones queued to send again.
    contents = [(f.filename or "upload", await f.read()) for f in incoming]
    rejected = [r for i, (name, body) in enumerate(contents) if (r := _rejection(i, name, body))]
    if rejected:
        status = 413 if all(r["code"] == "too_large" for r in rejected) else 422
        log.info("upload.rejected", count=len(rejected), of=len(contents),
                 codes=sorted({r["code"] for r in rejected}))
        return JSONResponse(
            status_code=status,
            content={"detail": "\n".join(r["reason"] for r in rejected), "rejected": rejected},
        )

    documents: list[dict[str, Any]] = list(case.documents) if case else []
    uploaded: list[UploadedDoc] = []
    for filename, content in contents:
        entry, api_doc = await _process_one(content, filename)
        if expected_type in _EXPECTED_FAMILIES:
            entry["expected_type"] = expected_type
        documents.append(entry)
        uploaded.append(api_doc)

    # Capture the pre-upload state BEFORE commit (async expire_on_commit would make these await-only
    # afterwards) — the trigger for re-running a needs_documents audit once the user has now
    # supplied every missing input.
    reaudit = (
        case is not None
        and case_file_id is not None
        and case.status == "audit_incomplete"
        and case.audit_incomplete_reason == "needs_documents"
    )
    # R1 (e2e round 3): a NEW bill on a case whose encounter facts were already read is the
    # explicit trigger for re-reading them — recorded answers carry over by fact_id and only a
    # new or changed charge is asked. (The thread screen's /extract on mount used to be the
    # accidental trigger, and it re-asked everything.)
    reread = (
        case is not None
        and case_file_id is not None
        and bool(case.line_items)
        and any(d.document_type in BILL_TYPES for d in uploaded)
    )
    if case is None:
        # An upload that opens a case IS the chat-first front door (doc 40 §D) — the guided
        # route creates its case in routes/intake.py and uploads into it by id.
        case = CaseFile(
            user_id=user.user_id, status="open", documents=documents, intake_mode="chat_first"
        )
        session.add(case)
    else:
        case.documents = documents  # reassign — SQLAlchemy doesn't track in-place JSONB mutation
    # an SBC names the plan year's start — kept on the coverage record for the retention
    # schedule (doc 43, decision 9), whichever front door the document came through
    from app.intake.timeline import persist_plan_year_start

    persist_plan_year_start(case)
    # The user's plan-level SBC (Settings → Plan documents) counts toward the checklist.
    from app.sources.plan_docs import plan_sbc_state

    _plan_sbc, _ = await plan_sbc_state(session, user.user_id)
    reaudit = reaudit and documents_all_satisfied(case, plan_sbc=_plan_sbc)  # …all satisfied now

    # Promote the typed provider / date-of-service onto the case (first structured hit wins; a
    # re-upload never overwrites an already-known value). The Record row reads these typed fields.
    if case.provider_name is None:
        case.provider_name = next(
            (d.get("provider_name") for d in documents if isinstance(d, dict) and d.get("provider_name")),
            None,
        )
    if case.date_of_service is None:
        _dos = next(
            (d.get("date_of_service") for d in documents if isinstance(d, dict) and d.get("date_of_service")),
            None,
        )
        if _dos:
            try:
                case.date_of_service = datetime.date.fromisoformat(str(_dos)[:10])
            except ValueError:
                pass
    if case.patient_name is None:
        case.patient_name = next(
            (d.get("patient_name") for d in documents if isinstance(d, dict) and d.get("patient_name")),
            None,
        )
    # Promote the typed call identifiers (B4), each from the document type that ASSIGNS it —
    # claim + payer phone from a payer-issued document, account + provider phone from a
    # provider-issued one. Same first-hit-wins rule as above: a re-upload never overwrites a
    # known value, and a field with no structured source stays NULL.
    _ids = derive_call_identifiers(documents)
    for _field, _value in _ids._asdict().items():
        if _value and getattr(case, _field) is None:
            setattr(case, _field, _value)
    # Attest-and-proceed trigger (§A2 state 1): extracted patient ≠ profile name flips the
    # case to attest_status='required' BEFORE encounter verification can proceed.
    _attest_user = (
        await session.execute(select(User).where(User.user_id == case.user_id))
    ).scalar_one_or_none()
    if _attest_user is not None:
        _was = case.attest_status
        if evaluate_attest_state(case, _attest_user) and _was != "required":
            from app.analytics.emit import emit as _emit

            await _emit(
                "attestation_required", user_id=case.user_id, case_file_id=case.case_file_id
            )
    # Dev-only fault injection for the e2e harness (app.faults): a synthetic user's upload
    # that OPENS a case may name one known fault; everywhere else the header is ignored.
    await session.flush()
    if case_file_id is None:
        from app.faults import FAULT_HEADER, accepted_fault, record_fault

        _fault = accepted_fault(
            request.headers.get(FAULT_HEADER),
            user_email=(_attest_user.email if _attest_user is not None else None),
        )
        if _fault:
            await record_fault(session, case.case_file_id, _fault)
    cfid = str(case.case_file_id)
    await session.commit()

    # Internal analytics (P0): the upload funnel is server-known. Best-effort, own sessions.
    from app.analytics.emit import emit
    from app.analytics.events import coerce_enum

    cf_uuid = UUID(cfid)
    await emit("upload_started", user_id=user.user_id, case_file_id=cf_uuid,
               properties={"file_count": len(incoming)})
    await emit("documents_accepted", user_id=user.user_id, case_file_id=cf_uuid,
               properties={"doc_count": len(uploaded)})
    for d in uploaded:
        dt = coerce_enum("extraction_succeeded", "doc_type", d.document_type or "unclassified")
        await emit("extraction_succeeded", user_id=user.user_id, case_file_id=cf_uuid,
                   properties={"doc_type": dt})
    if expected_type in _EXPECTED_FAMILIES:
        family = _EXPECTED_FAMILIES[expected_type]
        mismatched = [d for d in uploaded if (d.document_type or "unclassified") not in family]
        if mismatched:
            # Measured, not messaged: the wrongdoc VOICE for a per-item mismatch is Brock's
            # (A4 strings pending) — until then the expectation mismatch is an analytics
            # fact, and the checklist simply doesn't check the item off (have= derives from
            # the classifier's verdict, never the user's intent).
            await emit(
                "expected_document_mismatch", user_id=user.user_id, case_file_id=cf_uuid,
                properties={"expected": expected_type, "got_count": len(mismatched)},
            )

    if reaudit:
        # All missing documents provided → re-run the audit (finalize_audit sets audit_running,
        # then a terminal status). The results screen the user returns to polls status.
        log.info("upload.needs_documents_satisfied_reaudit", case_file_id=cfid)
        # Close-the-loop (flagship metric): the case's needs_documents request is satisfied.
        # Idempotent per case so it pairs 1:1 with document_request_issued.
        from app.analytics.emit import emit_idempotent

        await emit_idempotent("document_request_satisfied",
                              dedupe_key=f"document_request_satisfied:{cfid}",
                              user_id=user.user_id, case_file_id=cf_uuid)
        if not reread:
            background.add_task(finalize_audit, cfid)
    if reread:
        # the re-read decides: new facts → the user confirms them (the tap runs the audit);
        # nothing new → a needs_documents audit whose paper is now all in re-runs
        background.add_task(reread_for_new_document, cfid, then_audit=reaudit)

    log.info(
        "upload.processed",
        case_file_id=cfid,
        file_count=len(uploaded),
        document_types=[d.document_type for d in uploaded],
        attached_to_existing=case_file_id is not None,
    )

    if singular:
        first = uploaded[0]
        return UploadResponse(
            case_file_id=cfid,
            document_id=first.document_id,
            filename=first.filename,
            received_bytes=first.size_bytes,
            note=f"document_type={first.document_type}",
        )
    # Chat-first bootstrap (DL-91): a NEW case gets a thread (acknowledgment + live status card) and
    # the client routes there instead of the classic encounter screen. Flag-gated no-op (returns
    # None) — appended-to-existing uploads (case_file_id given) never bootstrap.
    conversation_id: str | None = None
    if case_file_id is None:
        from app.agents.thread_bridge import bootstrap_thread

        conversation_id = await bootstrap_thread(cfid)
    return MultiUploadResponse(
        case_file_id=cfid,
        uploads=uploaded,
        chat_first=conversation_id is not None,
        conversation_id=conversation_id,
    )
