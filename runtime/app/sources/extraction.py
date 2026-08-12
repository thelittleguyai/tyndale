"""V1-Lite OCR extraction engine + payload builders (the source-layer primitive).

``run_document_ocr`` runs Azure Document Intelligence (with stub fallback) on
uploaded bytes. ``extract_coverage_payload`` / ``extract_eob_payload`` turn that
OCR into the Coverage / EOB dict shapes the case file uses — the EXACT shapes the
``upload_extract_{coverage,eob}`` tools returned before CO-12A.

These live in app/sources/ (not app/tools/) so the data-interface adapters own
extraction without depending back on the tool layer. ``app.tools.ocr_tools`` (the
``bill_ocr_extract`` tool) and ``app.routes.upload`` call ``run_document_ocr``
from here. Logic moved verbatim from ocr_tools.py in CO-12A — behavior-identical.
"""

from __future__ import annotations

import asyncio
import base64
import re
from datetime import date
from typing import Any

import structlog

from app.config import get_settings
from app.stubs.ocr import stub_extract

log = structlog.get_logger(__name__)

# V1-Lite OCR is heuristic; both upload extractors report the same low confidence.
V1_LITE_OCR_CONFIDENCE = 0.3


def _read_bytes(args: dict[str, Any]) -> tuple[bytes, str]:
    """Tools accept either base64-encoded bytes or a local file path."""
    if "content_base64" in args:
        return base64.b64decode(args["content_base64"]), args.get("filename", "upload.bin")
    if "file_path" in args:
        with open(args["file_path"], "rb") as fh:
            return fh.read(), args["file_path"].rsplit("/", 1)[-1]
    raise ValueError("ocr tool requires content_base64 or file_path")


def _di_client():
    """Lazy-import the Azure DI client so import-time doesn't require the SDK.

    Returns None for any of:
      * endpoint or key unset
      * endpoint doesn't start with https:// (e.g. literal placeholder
        '<from terraform output>' values that got copied into .env.local)
    so callers can fall back to the stub instead of crashing on a bogus URL.
    """
    settings = get_settings()
    endpoint = settings.azure_doc_intelligence_endpoint or ""
    key = settings.azure_doc_intelligence_key or ""
    if not endpoint.startswith("https://") or not key or key.startswith("<"):
        log.warning(
            "ocr.di_endpoint_or_key_invalid_falling_back_to_stub",
            endpoint_set=bool(endpoint),
            endpoint_looks_real=endpoint.startswith("https://"),
            key_set=bool(key),
        )
        return None
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )


async def run_document_ocr(args: dict[str, Any]) -> dict[str, Any]:
    """Azure Document Intelligence prebuilt-document OCR (stub fallback).

    Backs the ``bill_ocr_extract`` tool and the upload route. Was
    ``ocr_tools._bill_ocr_extract`` before CO-12A."""
    settings = get_settings()
    content, filename = _read_bytes(args)

    if not settings.use_real_ocr:
        return stub_extract(filename, content)

    # Real OCR. A missing/invalid endpoint or a DI failure must DEGRADE to an error result —
    # NEVER fake stub text (that would fabricate document content under real OCR), and NEVER a
    # crash (an uncaught exception here 500s the request; a blocking call kills the replica).
    client = _di_client()
    if client is None:
        log.error("ocr.di_unavailable", filename=filename)
        return _ocr_error(filename, content, "di_credentials_missing")

    try:
        # The Azure DI SDK is SYNCHRONOUS — poller.result() blocks for seconds. Running it
        # inline in this async handler freezes the event loop, starving the health probe until
        # Container Apps restarts the replica mid-request (a 503 with no CORS). Offload to a
        # thread so the worker stays responsive.
        result = await asyncio.to_thread(_analyze_document, client, content)
    except Exception as exc:  # noqa: BLE001 — a DI failure degrades, never crashes the request
        log.error(
            "ocr.di_failed", filename=filename, error_class=type(exc).__name__, exc_info=True
        )
        return _ocr_error(filename, content, f"di_failed:{type(exc).__name__}")

    # Compact projection — keep the full Result accessible via 'raw' for the agent
    # to introspect via subsequent calls if it needs more.
    return {
        "filename": filename,
        "byte_count": len(content),
        "ocr_text": (result.content or "")[:50000],
        "extraction_status": "extracted",
        "pages": [
            {"page_number": p.page_number, "width": p.width, "height": p.height}
            for p in (result.pages or [])
        ],
        "key_value_pairs": [
            {
                "key": (kv.key.content if kv.key else None),
                "value": (kv.value.content if kv.value else None),
            }
            for kv in (result.key_value_pairs or [])
        ],
        "tables_count": len(result.tables or []),
    }


def _analyze_document(client, content: bytes):
    """Synchronous DI analyze — begin + block for the result. Runs in a worker thread (see
    run_document_ocr) so it never blocks the event loop.

    Uses the configured model (default 'prebuilt-layout'). The legacy 'prebuilt-document' was
    removed in the GA API (2024-11-30) and 404s — 'prebuilt-layout' + the KEY_VALUE_PAIRS add-on
    is its successor and returns the same content/pages/tables/key_value_pairs projection."""
    from azure.ai.documentintelligence.models import DocumentAnalysisFeature

    settings = get_settings()
    poller = client.begin_analyze_document(
        settings.azure_doc_intelligence_model,
        body=content,
        features=[DocumentAnalysisFeature.KEY_VALUE_PAIRS],
    )
    return poller.result()


def _ocr_error(filename: str, content: bytes, reason: str) -> dict[str, Any]:
    """A soft OCR failure under real OCR: empty text + extraction_status='error'. The caller
    persists the document and degrades (Grounding Doctrine) — never fabricated text."""
    return {
        "filename": filename,
        "byte_count": len(content),
        "ocr_text": "",
        "extraction_status": "error",
        "error": reason,
        "pages": [],
        "key_value_pairs": [],
        "tables_count": 0,
    }


def _grep(text: str, prefixes: tuple[str, ...]) -> str | None:
    for p in prefixes:
        idx = text.find(p)
        if idx >= 0:
            after = text[idx + len(p) :].strip()
            return after.splitlines()[0].strip() if after else None
    return None


# Anchors that reliably precede the servicing provider / facility name on a bill or EOB.
_PROVIDER_ANCHORS = (
    "PROVIDER NAME", "RENDERING PROVIDER", "SERVICING PROVIDER", "PROVIDER/FACILITY",
    "BILLED BY", "BILL FROM", "REMIT TO", "FACILITY", "PROVIDER",
)


# Patient/member anchors (attest-and-proceed §3): who the document is ABOUT, extracted TYPED at
# parse time (DL-39) so the name-mismatch trigger never regexes finding prose. Order matters —
# specific anchors before the bare "PATIENT".
_PATIENT_ANCHORS = (
    "PATIENT NAME", "MEMBER NAME", "BENEFICIARY NAME", "SUBSCRIBER NAME",
    "PATIENT:", "MEMBER:", "PATIENT",
)


# A SECOND field sharing the anchor's line ("Patient: JANE DOE Account #: 123"). An explicit
# label list, not a greedy pattern — a greedy one eats name words ("JANE DOE Account" -> "JANE").
_SECOND_FIELD_RE = re.compile(
    r"\s+(?:ACCOUNT|ACCT|DOB|DATE OF BIRTH|MEMBER|MEMBER ID|ID|MRN|NPI|CLAIM|GROUP|POLICY|"
    r"SUBSCRIBER|PLAN|TAX ID|PHONE|DATE)\b\s*#?\s*:",
    re.IGNORECASE,
)


def _grep_anchored_name(text: str, anchors: tuple[str, ...]) -> str | None:
    """Best-effort TYPED name from OCR text — matched CASE-INSENSITIVELY on a known anchor but
    returned in the ORIGINAL case ("Maple Grove Family Medicine"). Conservative: a line that
    doesn't look like a name (too short/long, mostly digits/punctuation) returns None, so the
    failure mode is a null (→ caller's fallback), never a wrong name."""
    if not text:
        return None
    upper = text.upper()
    for a in anchors:
        idx = upper.find(a)
        if idx < 0:
            continue
        line = text[idx + len(a) :].splitlines()[0] if idx + len(a) < len(text) else ""
        line = line.lstrip(":-–—# \t").strip()
        # Documents commonly put a SECOND field on the same line ("Patient: JANE DOE
        # Account #: 12345", "Provider: CLINIC   NPI: 999"). Keep only the first column —
        # a real name never contains a run of 2+ spaces, a tab, or a trailing "<Label>:".
        line = re.split(r"\s{2,}|\t", line)[0].strip()
        line = _SECOND_FIELD_RE.split(line)[0].strip()
        # Name sanity: has letters, reasonable length, not mostly digits/punctuation/dates.
        if line and 3 <= len(line) <= 80 and re.search(r"[A-Za-z]{2,}", line) and not _DATE_RE.search(line):
            letters = sum(c.isalpha() for c in line)
            if letters >= max(3, len(line) // 2):
                return line
    return None


def grep_provider_name(text: str) -> str | None:
    """Typed provider name from OCR text (record-row title). See _grep_anchored_name."""
    return _grep_anchored_name(text, _PROVIDER_ANCHORS)


def grep_patient_name(text: str) -> str | None:
    """Typed patient/member name from OCR text (attest-and-proceed trigger). Fails to None —
    a missing patient name never fabricates a mismatch. See _grep_anchored_name."""
    return _grep_anchored_name(text, _PATIENT_ANCHORS)


# --- Typed case identifiers (delta B4 / conformance H6-L7) --------------------------------
# The claim number and account number the user must read aloud on the call. Extracted TYPED at
# parse time (DL-39), same discipline as provider_name: the call script cites a stored field,
# never a number regexed back out of finding prose at render time.
#
# Which lives where: a CLAIM number is assigned by the payer and prints on the EOB/remittance;
# an ACCOUNT (or statement/guarantor) number is assigned by the provider and prints on the
# bill. A case with three EOBs has three claim numbers — hence per-document extraction, with
# the case-level column carrying the primary (see `case_files.claim_number`).
_CLAIM_ANCHORS = (
    "CLAIM NUMBER", "CLAIM NO.", "CLAIM NO", "CLAIM #", "CLAIM ID", "CLAIM REFERENCE",
    "DOCUMENT CONTROL NUMBER", "DCN", "CLAIM:",
)
_ACCOUNT_ANCHORS = (
    "ACCOUNT NUMBER", "ACCOUNT NO.", "ACCOUNT NO", "ACCOUNT #", "ACCT NUMBER", "ACCT NO.",
    "ACCT NO", "ACCT #", "PATIENT ACCOUNT", "GUARANTOR ACCOUNT", "STATEMENT NUMBER",
    "ACCOUNT:", "ACCT:", "RE: ACCOUNT",  # collections notices lead with the account this way
)

# An identifier token: alphanumeric with optional separators, 4–30 chars ("1821709",
# "TST20260514", "24-A88301-01"). The charset excludes "$", "," and "." so a money amount can
# never match as one token, and a date is rejected explicitly below.
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]{3,29}")

# A US phone anywhere in a line, with the optional long-distance 1. Both leading groups start
# 2-9 (no real area/exchange code starts 0 or 1), which keeps ID digit-runs from reading as
# phone numbers.
_PHONE_RE = re.compile(r"(?:\b1[-.\s])?\(?\b[2-9]\d{2}\)?[-.\s]?[2-9]\d{2}[-.\s]?\d{4}\b")

# Anchors that mark a number as the document's CONTACT number — the one printed for the reader
# to call. A phone is extracted ONLY after one of these: never inferred from a bare digit run,
# and never looked up externally. Whether it belongs to the provider or the payer is decided by
# the DOCUMENT TYPE at the call site (a bill's contact number is the provider's, an EOB's is
# the payer's) — never guessed from the wording.
_CONTACT_ANCHORS = (
    "QUESTIONS ABOUT YOUR BILL", "QUESTIONS ABOUT THIS BILL", "BILLING QUESTIONS",
    "BILLING OFFICE", "PATIENT ACCOUNTS", "PATIENT FINANCIAL SERVICES", "CUSTOMER SERVICE",
    "MEMBER SERVICES", "CUSTOMER SERVICE:", "QUESTIONS ABOUT THIS CLAIM", "QUESTIONS?",
    "CONTACT US", "CALL US AT", "CALL US", "PLEASE CALL", "TELEPHONE", "PHONE", "TEL",
)


def _looks_like_identifier(token: str) -> bool:
    """A claim/account number: has a digit, has no date/phone shape, isn't a label word."""
    if not (4 <= len(token) <= 30) or not any(c.isdigit() for c in token):
        return False
    if _DATE_RE.search(token) or _PHONE_RE.search(token):
        return False
    # A bare 10/11-digit run is far more likely a phone than an account number; a real
    # identifier of that length almost always carries a letter or a separator.
    digits = re.sub(r"\D", "", token)
    return not (len(digits) == len(token) and len(digits) in (10, 11))


def _grep_identifier(text: str, anchors: tuple[str, ...]) -> str | None:
    """Typed identifier following a known anchor, or None.

    Looks at the anchor's own line first (``Account #: 1821709``), then the line below it
    (label-above-value layouts). Anything failing `_looks_like_identifier` yields None — the
    failure mode is a null the caller degrades on, never a wrong number read aloud on a call.
    """
    if not text:
        return None
    upper = text.upper()
    for a in anchors:
        idx = upper.find(a)
        if idx < 0:
            continue
        rest = text[idx + len(a) :]
        lines = rest.splitlines()
        for candidate_line in (lines[0] if lines else "", lines[1] if len(lines) > 1 else ""):
            stripped = candidate_line.lstrip(":-–—# \t")
            # Spans occupied by a phone number, so a formatted one can't be read as an
            # identifier a piece at a time — "(608) 364-5011" must not yield "364-5011".
            phone_spans = [m.span() for m in _PHONE_RE.finditer(stripped)]
            for m in _IDENTIFIER_RE.finditer(stripped):
                if any(m.start() < end and start < m.end() for start, end in phone_spans):
                    continue
                token = m.group(0).strip("-/")
                if _looks_like_identifier(token):
                    return token
            # Only fall through to the next line when THIS one held no digits at all; a line
            # with a number we rejected (a date, a phone) means the anchor's value is not an
            # identifier, and the line below belongs to a different field.
            if any(c.isdigit() for c in stripped):
                break
    return None


def grep_claim_number(text: str) -> str | None:
    """Typed payer-assigned claim number from an EOB. None when no anchored value. DL-39."""
    return _grep_identifier(text, _CLAIM_ANCHORS)


def grep_account_number(text: str) -> str | None:
    """Typed provider-assigned account/statement number from a bill. None when absent. DL-39."""
    return _grep_identifier(text, _ACCOUNT_ANCHORS)


def grep_contact_phone(text: str) -> str | None:
    """The contact number PRINTED ON this document, as printed, or None.

    Requires a contact anchor — a phone-shaped digit run on its own is not evidence that it is
    the number to call. Nothing is ever looked up externally: if the document doesn't print a
    number, the user doesn't get a dial button.
    """
    if not text:
        return None
    upper = text.upper()
    for a in _CONTACT_ANCHORS:
        idx = upper.find(a)
        if idx < 0:
            continue
        # Same line, else the line below (labels commonly sit above their number).
        lines = text[idx + len(a) :].splitlines()
        window = "\n".join(lines[:2])
        m = _PHONE_RE.search(window)
        if m:
            return m.group(0).strip()
    return None


def _first_dollar(text: str, anchors: tuple[str, ...]) -> float | None:
    upper = text.upper()
    for anchor in anchors:
        idx = upper.find(anchor)
        if idx < 0:
            continue
        window = text[idx : idx + 200]
        m = re.search(r"\$?\s*([0-9]{1,3}(?:[,0-9]{0,9})?(?:\.[0-9]{2})?)", window)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}")


def _to_iso(raw: str) -> str | None:
    """Normalize a matched date token to ISO (YYYY-MM-DD), or None if unparseable."""
    s = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        mo, d, y = (int(g) for g in m.groups())
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def _grep_date(text: str, anchors: tuple[str, ...]) -> str | None:
    """First date token following any anchor, normalized to ISO. None if absent."""
    upper = text.upper()
    for anchor in anchors:
        idx = upper.find(anchor)
        if idx < 0:
            continue
        m = _DATE_RE.search(text[idx : idx + 120])
        if m:
            iso = _to_iso(m.group(0))
            if iso:
                return iso
    return None


def _network_status(text: str) -> str | None:
    """'out' if the EOB mentions out-of-network, 'in' if in-network, else None."""
    u = text.upper()
    if "OUT-OF-NETWORK" in u or "OUT OF NETWORK" in u or "NON-NETWORK" in u:
        return "out"
    if "IN-NETWORK" in u or "IN NETWORK" in u:
        return "in"
    return None


async def extract_coverage_payload(args: dict[str, Any]) -> dict[str, Any]:
    """Coverage dict from an uploaded insurance card — the pre-CO-12A
    ``upload_extract_coverage`` return: {coverage, coverage_terms_confidence, raw_ocr}.

    Walking skeleton parses the OCR'd insurance-card text heuristically; real field
    extraction with per-value confidence surfaces in the encounter-verification UI."""
    raw = await run_document_ocr(args)
    text = (raw.get("ocr_text") or "").upper()

    coverage = {
        "plan_name": _grep(text, ("PLAN:", "PLAN NAME:", "GROUP NAME:")),
        "payer_name": _grep(text, ("PAYER:", "INSURER:", "INSURANCE:")),
        "member_id": _grep(text, ("MEMBER ID:", "ID:", "SUBSCRIBER ID:")),
        "deductible_amount": None,
        "deductible_met": None,
        "coinsurance_percent": None,
        "oop_max_amount": None,
        "oop_max_met": None,
        "network_tier": None,
    }
    return {
        "coverage": coverage,
        "coverage_terms_confidence": {
            "overall": V1_LITE_OCR_CONFIDENCE,
            "notes": "V1-Lite OCR heuristics; user should confirm via encounter-verification UI",
        },
        "raw_ocr": raw,
    }


async def extract_eob_payload(args: dict[str, Any]) -> dict[str, Any]:
    """EOB dict from an uploaded EOB — {eob, raw_ocr}.

    The pre-CO-12A core keys (claim_id, billed_amount, allowed_amount,
    patient_responsibility, remark_codes) are unchanged. CO-12B adds best-effort
    heuristic fields the accumulator engine consumes; all are low-confidence and
    None when not found (never guess a number/date)."""
    raw = await run_document_ocr(args)
    text = raw.get("ocr_text") or ""

    return {
        "eob": {
            "claim_id": _grep(text.upper(), ("CLAIM:", "CLAIM ID:")),
            "billed_amount": _first_dollar(text, ("BILLED",)),
            "allowed_amount": _first_dollar(text, ("ALLOWED",)),
            "patient_responsibility": _first_dollar(
                text, ("PATIENT RESPONSIBILITY", "YOU OWE", "MEMBER RESPONSIBILITY")
            ),
            "remark_codes": [],
            # --- CO-12B additive: accumulator-reconstruction inputs (heuristic, low-confidence) ---
            "adjudication_date": _grep_date(
                text, ("DATE PROCESSED", "PROCESSED ON", "ADJUDICATED", "PROCESSED")
            ),
            "date_of_service": _grep_date(text, ("DATE OF SERVICE", "SERVICE DATE", "DOS")),
            "amount_applied_to_deductible": _first_dollar(
                text, ("APPLIED TO DEDUCTIBLE", "DEDUCTIBLE APPLIED")
            ),
            "amount_applied_to_oop": _first_dollar(
                text, ("APPLIED TO OUT-OF-POCKET", "APPLIED TO OOP", "OUT-OF-POCKET APPLIED")
            ),
            "network_status": _network_status(text),
            "deductible_ytd_stated": _first_dollar(
                text, ("DEDUCTIBLE YTD", "YTD DEDUCTIBLE", "DEDUCTIBLE MET TO DATE")
            ),
            "oop_ytd_stated": _first_dollar(
                text, ("OUT-OF-POCKET YTD", "YTD OUT-OF-POCKET", "OOP MET TO DATE")
            ),
        },
        "raw_ocr": raw,
    }
