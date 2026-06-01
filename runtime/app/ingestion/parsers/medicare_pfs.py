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

# CMS PFS conversion factor. The parser reads the authoritative value straight from the
# PPRRVU file's CONV FACTOR column when present; this constant is only a fallback. CMS
# publishes a new CF each year — 33.4009 for 2026 (confirmed from the live file); verify
# annually per DL-67.
DEFAULT_CONVERSION_FACTOR = 33.4009

# "code" is deliberately NOT an HCPCS alias: the real PPRRVU file has a separate "CODE"
# (status) column distinct from "HCPCS".
_HCPCS_ALIASES = ("hcpcs", "hcpcs_code", "hcpcs cd")
# The FIRST header column matching one of these is the total RVU. In the real PPRRVU the
# column is simply "total" and there are two (non-facility then facility) — left-to-right
# scanning selects the non-facility total, which is the office-setting allowable.
_TOTAL_RVU_ALIASES = (
    "non_fac_total",
    "non-facility total",
    "nonfacility total",
    "total_rvu",
    "total",
)
_MOD_ALIASES = ("modifier", "mod")
_CF_ALIASES = ("factor", "conv factor", "conversion factor", "cf")


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


class MedicarePfsParser(BulkSourceParser):
    source_name = "medicare_pfs"

    def __init__(self, year: int, conversion_factor: float = DEFAULT_CONVERSION_FACTOR) -> None:
        self.year = year
        self.cf = conversion_factor

    async def parse_file(self, blob_path: str, blob_storage) -> AsyncIterator[ParsedRecord]:
        raw = await blob_storage.read_bytes(blob_path)
        rows = list(csv.reader(io.StringIO(_decode(raw))))

        # The real PPRRVU file has ~9 preamble rows (title, copyright, release date) before
        # the column-header row whose first cell is "HCPCS". Locate it (DictReader can't —
        # the header carries duplicate "TOTAL"/"RVU" names that would collapse).
        header_idx = next(
            (
                i
                for i, row in enumerate(rows)
                if row and (row[0] or "").strip().lower() in _HCPCS_ALIASES
            ),
            None,
        )
        if header_idx is None:
            log.warning("medicare_pfs.no_header_row", blob_path=blob_path)
            return
        header = [(c or "").strip().lower() for c in rows[header_idx]]

        def first_idx(aliases: tuple[str, ...]) -> int | None:
            return next((i for i, name in enumerate(header) if name in aliases), None)

        code_i = first_idx(_HCPCS_ALIASES)
        total_i = first_idx(_TOTAL_RVU_ALIASES)  # first "TOTAL" = non-facility in PPRRVU
        mod_i = first_idx(_MOD_ALIASES)
        cf_i = first_idx(_CF_ALIASES)
        if code_i is None or total_i is None:
            log.warning("medicare_pfs.columns_missing", header=header[:12])
            return

        seen: set[str] = set()
        for row in rows[header_idx + 1 :]:
            if len(row) <= total_i:
                continue
            code = (row[code_i] or "").strip()
            if not code or code in seen:
                continue
            if mod_i is not None and mod_i < len(row) and (row[mod_i] or "").strip():
                continue  # skip modifier-specific rows; use the base code once
            total_rvu = _num(row[total_i])
            if not total_rvu or total_rvu <= 0:
                continue  # status I/J/anesthesia rows carry no RVU-based allowable
            cf = self.cf
            if cf_i is not None and cf_i < len(row):
                file_cf = _num(row[cf_i])
                if file_cf and 10.0 <= file_cf <= 100.0:
                    cf = file_cf  # authoritative CF straight from the file
            seen.add(code)
            yield RateRecord(
                code=code,
                rate=compute_allowable(total_rvu, cf),
                rate_type="allowable",
                source="medicare_pfs",
                code_type="HCPCS",
                payer=None,
                location_zip3=None,  # national baseline (GPCI=1.0)
                effective_year=self.year,
                raw_metadata={"total_rvu": total_rvu, "conversion_factor": cf},
            )
