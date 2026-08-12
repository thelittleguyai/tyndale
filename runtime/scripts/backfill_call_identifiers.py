"""One-shot backfill for the case call identifiers (delta B4, 2026-08-12).

Fills `claim_number` / `account_number` / `provider_phone` / `payer_phone` on EXISTING cases
from STRUCTURED extraction artifacts only, in this order:

1. the typed per-document fields a newer upload already wrote (`derive_call_identifiers`);
2. the document's own OCR preview, re-run through the same parse-time greps;
3. the legacy EOB payload's `claim_id` (pre-B4 `extract_eob_payload`), validated through the
   same identifier sanity check — that field holds the whole rest of the line, so only its
   first token survives, and only if it looks like an identifier.

It never regexes an identifier out of finding prose, never infers a phone from a bare digit
run, and never looks a number up externally. A case with no structured source keeps NULLs —
the call script then degrades rather than quoting a number we guessed.

Usage: uv run python scripts/backfill_call_identifiers.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/ on the path

from sqlalchemy import select  # noqa: E402

from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.models.case_files import CaseFile  # noqa: E402
from app.sources.call_identifiers import CallIdentifiers, derive_call_identifiers  # noqa: E402
from app.sources.document_classifier import (  # noqa: E402
    PAYER_ISSUED_TYPES,
    PROVIDER_ISSUED_TYPES,
)
from app.sources.extraction import (  # noqa: E402
    _looks_like_identifier,
    grep_account_number,
    grep_claim_number,
    grep_contact_phone,
)

_FIELDS = ("claim_number", "account_number", "provider_phone", "payer_phone")


def _from_previews(docs: list[dict]) -> CallIdentifiers:
    """Re-run the parse-time greps over each document's stored OCR preview.

    Same type routing as live promotion: an identifier is only attributed to the party whose
    document type assigns it, so a claim number is never taken off a provider's bill.
    """
    claim = account = provider_phone = payer_phone = None
    for d in docs:
        text = d.get("ocr_text_preview") or ""
        if not text:
            continue
        doc_type = d.get("document_type")
        if doc_type in PAYER_ISSUED_TYPES:
            claim = claim or grep_claim_number(text)
            payer_phone = payer_phone or grep_contact_phone(text)
        elif doc_type in PROVIDER_ISSUED_TYPES:
            account = account or grep_account_number(text)
            provider_phone = provider_phone or grep_contact_phone(text)
    return CallIdentifiers(claim, account, provider_phone, payer_phone)


def _legacy_eob_claim(eobs) -> str | None:
    """`eob.claim_id` from the pre-B4 extractor — its first token, only if it validates.

    That field was grepped as "rest of the uppercased line", so it routinely carries trailing
    junk ("TST20260514  DOS 05/14/2026"). Taking the first token and putting it through
    `_looks_like_identifier` keeps a real claim number and drops everything else.
    """
    for e in eobs or []:
        if not isinstance(e, dict):
            continue
        raw = e.get("claim_id") or (e.get("eob") or {}).get("claim_id")
        if isinstance(raw, str) and raw.strip():
            token = raw.strip().split()[0].strip(":#-/")
            if _looks_like_identifier(token):
                return token
    return None


def derive_identifiers(case) -> CallIdentifiers:
    """The four typed identifiers for one existing case, from structured artifacts only."""
    docs = [d for d in (case.documents or []) if isinstance(d, dict)]
    typed = derive_call_identifiers(docs)
    grepped = _from_previews(docs)
    return CallIdentifiers(
        claim_number=typed.claim_number or grepped.claim_number or _legacy_eob_claim(case.eobs),
        account_number=typed.account_number or grepped.account_number,
        provider_phone=typed.provider_phone or grepped.provider_phone,
        payer_phone=typed.payer_phone or grepped.payer_phone,
    )


async def run_backfill(dry_run: bool = False) -> dict[str, int]:
    counts = dict.fromkeys(_FIELDS, 0)
    scanned = 0
    async with AsyncSessionLocal() as s:
        cases = (await s.execute(select(CaseFile))).scalars().all()
        for case in cases:
            scanned += 1
            if all(getattr(case, f) is not None for f in _FIELDS):
                continue
            derived = derive_identifiers(case)
            for field, value in derived._asdict().items():
                if value and getattr(case, field) is None:
                    setattr(case, field, value)
                    counts[field] += 1
        if not dry_run:
            await s.commit()
    return {"scanned": scanned, **counts}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(f"backfill: {asyncio.run(run_backfill(dry_run=args.dry_run))}")
