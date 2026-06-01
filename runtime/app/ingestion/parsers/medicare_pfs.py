"""Medicare Physician Fee Schedule (PFS) RVU parser (Phase CO-3A).

VERIFY at implementation time: CMS publishes the PFS Relative Value Files at
cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files (page
confirmed live 2026-05-30) — a per-year ZIP containing a PPRRVU CSV. The exact
column headers shift year to year, so column lookup is alias-based.

Medicare allowable = TOTAL_RVU × Conversion Factor × GPCI. This parser computes
the NATIONAL allowable (GPCI = 1.0); per-locality GPCI expansion is a refinement
(location_zip3 stays null = national baseline). The Conversion Factor is a yearly
CMS constant passed in (default below — verify the current-year value).
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator

import structlog

from app.ingestion.parsers import BulkSourceParser, ParsedRecord, RateRecord

log = structlog.get_logger(__name__)

# CMS PFS conversion factor — verify per year (this is the documented 2026 value).
DEFAULT_CONVERSION_FACTOR = 32.3465

_HCPCS_ALIASES = ("hcpcs", "hcpcs_code", "code", "hcpcs cd")
_TOTAL_RVU_ALIASES = (
    "non_fac_total",
    "non-facility total",
    "nonfacility total",
    "total_rvu",
    "fac_total",
    "facility total",
    "total",
)
_MOD_ALIASES = ("modifier", "mod")


def compute_allowable(total_rvu: float, conversion_factor: float, gpci: float = 1.0) -> float:
    return round(total_rvu * conversion_factor * gpci, 2)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _num(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _pick(row: dict, aliases: tuple[str, ...]) -> str | None:
    for a in aliases:
        if row.get(a) not in (None, ""):
            return row[a]
    return None


class MedicarePfsParser(BulkSourceParser):
    source_name = "medicare_pfs"

    def __init__(self, year: int, conversion_factor: float = DEFAULT_CONVERSION_FACTOR) -> None:
        self.year = year
        self.cf = conversion_factor

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        raw = await blob_storage.read_bytes(blob_path)
        reader = csv.DictReader(io.StringIO(_decode(raw)))
        seen: set[str] = set()
        for row in reader:
            r = {(k or "").strip().lower(): v for k, v in row.items()}
            code = _pick(r, _HCPCS_ALIASES)
            if not code:
                continue
            code = code.strip()
            # Skip modifier-specific rows for the baseline (use the base code once).
            mod = _pick(r, _MOD_ALIASES)
            if mod and str(mod).strip():
                continue
            total_rvu = _num(_pick(r, _TOTAL_RVU_ALIASES))
            if total_rvu is None or code in seen:
                continue
            seen.add(code)
            yield RateRecord(
                code=code,
                rate=compute_allowable(total_rvu, self.cf),
                rate_type="allowable",
                source="medicare_pfs",
                code_type="HCPCS",
                payer=None,
                location_zip3=None,  # national baseline (GPCI=1.0)
                effective_year=self.year,
                raw_metadata={"total_rvu": total_rvu, "conversion_factor": self.cf},
            )
