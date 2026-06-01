"""Hospital machine-readable-file (MRF) parser (Phase CO-3A).

CMS Hospital Price Transparency Final Rule: each hospital publishes a
machine-readable file. The v2.0 JSON schema nests
standard_charge_information[].standard_charges[].payers_information[]. Hospitals
vary in exact paths/format (some publish CSV), so key lookup is alias-based and
the parser tolerates missing branches. VERIFY per-hospital format at curation
time. Large files: json.load for now (small in tests); ijson streaming is a
refinement for multi-GB hospitals (noted in README).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog

from app.ingestion.parsers import BulkSourceParser, ParsedRecord, RateRecord

log = structlog.get_logger(__name__)

_NEG_ALIASES = (
    "standard_charge_dollar",
    "standard_charge_negotiated",
    "negotiated_dollar",
    "negotiated_rate",
)
_CASH_ALIASES = ("discounted_cash", "standard_charge_cash", "cash_price")
_GROSS_ALIASES = ("gross_charge", "standard_charge_gross")


def _pick(d: dict, aliases: tuple[str, ...]):
    for a in aliases:
        if d.get(a) not in (None, ""):
            return d[a]
    return None


def _num(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return round(float(str(v).replace(",", "").replace("$", "").strip()), 2)
    except (ValueError, TypeError):
        return None


class HospitalMrfParser(BulkSourceParser):
    source_name = "hospital_mrf"

    def __init__(self, hospital_id: str) -> None:
        self.hospital_id = hospital_id

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        raw = await blob_storage.read_bytes(blob_path)
        try:
            doc = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            log.warning("hospital_mrf.not_json", blob_path=blob_path)
            return

        items = doc.get("standard_charge_information") or doc.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            codes = item.get("code_information") or item.get("codes") or []
            code, code_type = _first_code(codes, item)
            if not code:
                continue
            for sc in item.get("standard_charges") or [item]:
                if not isinstance(sc, dict):
                    continue
                cash = _num(_pick(sc, _CASH_ALIASES))
                gross = _num(_pick(sc, _GROSS_ALIASES))
                if cash is not None:
                    yield self._rate(code, code_type, None, cash, "cash")
                if gross is not None:
                    yield self._rate(code, code_type, None, gross, "gross")
                for payer in sc.get("payers_information") or []:
                    if not isinstance(payer, dict):
                        continue
                    neg = _num(_pick(payer, _NEG_ALIASES))
                    if neg is not None:
                        yield self._rate(
                            code,
                            code_type,
                            payer.get("payer_name"),
                            neg,
                            "negotiated",
                            plan=payer.get("plan_name"),
                        )

    def _rate(self, code, code_type, payer, rate, rate_type, plan=None) -> RateRecord:
        return RateRecord(
            code=str(code),
            rate=rate,
            rate_type=rate_type,
            source="hospital_mrf",
            code_type=code_type,
            payer=payer,
            hospital_id=self.hospital_id,
            raw_metadata={"plan_name": plan} if plan else {},
        )


def _first_code(codes: list, item: dict) -> tuple[str | None, str | None]:
    for c in codes or []:
        if isinstance(c, dict) and c.get("code"):
            return str(c["code"]), c.get("type") or c.get("code_type")
    # Flat fallback (CSV-style row promoted to a dict).
    if item.get("code"):
        return str(item["code"]), item.get("code_type") or item.get("type")
    return None, None
