"""Transparency-in-Coverage (TiC) in-network MRF parser (Phase CO-3A).

CMS TiC rule: payers publish per-plan in-network rate files (JSON-Lines, often
gzipped; the corpus is ~100 TB across all payers). This streams records so a
multi-GB file never fully loads into memory.

Each in-network record (CMS TiC schema):
  { negotiation_arrangement, name, billing_code_type, billing_code,
    negotiated_rates: [{ negotiated_prices: [{ negotiated_type, negotiated_rate,
      expiration_date, billing_class }], provider_groups: [...] }] }

VERIFY each payer's current index/file URL at implementation time (payers rotate
them). Some payers ship one giant JSON object with an `in_network` array rather
than JSONL — both are handled.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import AsyncIterator

import structlog

from app.ingestion.parsers import BulkSourceParser, ParsedRecord, RateRecord

log = structlog.get_logger(__name__)

_RATE_TYPES_KEPT = {"negotiated", "fee schedule", "fee_schedule"}


class TicMrfParser(BulkSourceParser):
    source_name = "tic_mrf"

    def __init__(self, payer: str, effective_year: int) -> None:
        self.payer = payer
        self.effective_year = effective_year

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        path = await blob_storage.materialize_local(blob_path)
        opener = gzip.open if path.endswith(".gz") else open

        jsonl_records: list[dict] = []
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip().rstrip(",")
                if not line or line in ("[", "]", "{", "}"):
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    # Not line-delimited — fall back to reading the whole file once.
                    break
                if isinstance(obj, dict) and obj.get("billing_code"):
                    jsonl_records.append(obj)

        if jsonl_records:
            for rec in jsonl_records:
                async for r in self._emit(rec):
                    yield r
            return

        # Single-JSON-object fallback (in_network array).
        raw = await blob_storage.read_bytes(blob_path)
        if path.endswith(".gz"):
            raw = gzip.decompress(raw)
        try:
            doc = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            log.warning("tic_mrf.unparseable", blob_path=blob_path)
            return
        for rec in doc.get("in_network", []) if isinstance(doc, dict) else []:
            if isinstance(rec, dict) and rec.get("billing_code"):
                async for r in self._emit(rec):
                    yield r

    async def _emit(self, rec: dict) -> AsyncIterator[ParsedRecord]:
        code = str(rec.get("billing_code"))
        code_type = rec.get("billing_code_type")
        for nr in rec.get("negotiated_rates") or []:
            if not isinstance(nr, dict):
                continue
            for price in nr.get("negotiated_prices") or []:
                if not isinstance(price, dict):
                    continue
                ntype = str(price.get("negotiated_type", "")).lower()
                rate = price.get("negotiated_rate")
                if rate is None or (ntype and ntype not in _RATE_TYPES_KEPT):
                    continue
                try:
                    rate_f = round(float(rate), 2)
                except (ValueError, TypeError):
                    continue
                yield RateRecord(
                    code=code,
                    rate=rate_f,
                    rate_type="negotiated",
                    source="tic_mrf",
                    code_type=code_type,
                    payer=self.payer,
                    effective_year=self.effective_year,
                    raw_metadata={
                        "billing_class": price.get("billing_class"),
                        "expiration_date": price.get("expiration_date"),
                    },
                )
