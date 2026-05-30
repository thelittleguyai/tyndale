"""CMS Medicare Coverage Database (MCD) discovery + extraction (Phase CO-2A).

NCDs (national) and LCDs (MAC/state-level) are public-domain Medicare coverage
rules. This module discovers them from the MCD and parses their documents into a
section structure the rest of the pipeline (extract → chunk → embed → upsert)
consumes.

SOURCE-SHAPE ASSUMPTION (verify before first live run): the MCD exposes
machine-readable report endpoints returning JSON rows; this module targets that
JSON API rather than scraping HTML index tables (more robust + the documented
machine-readable source). The exact field names below are modeled on the MCD
report schema and MUST be confirmed against the live API the first time
VOYAGE_API_KEY/live ingestion runs — the parse_* functions are isolated from the
fetch_* functions precisely so the response shape can be re-pointed without
touching the pipeline. Document bodies are parsed from HTML via stdlib
(no new dependency). NCD/LCD text is public domain; per DL-54 we store code
NUMBERS as facts but never synthesize AMA CPT descriptors.

Throttling/robots: max 5 concurrent requests, 200ms baseline spacing, a
descriptive User-Agent, and a best-effort robots.txt check (urllib.robotparser).
"""

from __future__ import annotations

import asyncio
import datetime
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

import httpx
import structlog

log = structlog.get_logger(__name__)

MCD_BASE = "https://www.cms.gov/medicare-coverage-database"
# MCD machine-readable report endpoints (shape assumed — see module docstring).
NCD_INDEX_URL = f"{MCD_BASE}/api/reports/ncd-list"
LCD_INDEX_URL = f"{MCD_BASE}/api/reports/lcd-list"
NCD_DOC_URL = f"{MCD_BASE}/view/ncd.aspx"  # ?ncdid=...
LCD_DOC_URL = f"{MCD_BASE}/view/lcd.aspx"  # ?lcdid=...

_USER_AGENT = (
    "TyndaleBot/1.0 (+https://tyndaleapp.net; medical-billing-advocacy; contact ops@tyndaleapp.net)"
)
_MAX_CONCURRENCY = 5
_THROTTLE_SECONDS = 0.2
_TIMEOUT = 30.0

_sema = asyncio.Semaphore(_MAX_CONCURRENCY)

# Code-extraction regexes (facts on the source document; DL-54: numbers only).
_CPT_RE = re.compile(r"\b\d{5}\b")
_HCPCS_RE = re.compile(r"\b[A-V]\d{4}\b")
_ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b")


# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #
@dataclass
class NcdSummary:
    ncd_id: str
    title: str
    effective_date: str | None
    last_modified: str | None
    document_url: str


@dataclass
class LcdSummary:
    lcd_id: str
    title: str
    mac: str | None
    state: str | None
    effective_date: str | None
    last_modified: str | None
    document_url: str


@dataclass
class PolicySection:
    heading: str
    body: str
    applicable_codes: list[str] = field(default_factory=list)
    section_number: str | None = None


@dataclass
class NcdDocument:
    ncd_id: str
    title: str
    full_text: str
    sections: list[PolicySection]
    effective_date: str | None = None
    last_modified: str | None = None
    parent_part: str | None = None
    parent_subpart: str | None = None

    @property
    def policy_id(self) -> str:
        return f"NCD-{self.ncd_id}"


@dataclass
class LcdDocument:
    lcd_id: str
    title: str
    mac: str | None
    state: str | None
    full_text: str
    sections: list[PolicySection]
    effective_date: str | None = None
    last_modified: str | None = None
    parent_part: str | None = None
    parent_subpart: str | None = None

    @property
    def policy_id(self) -> str:
        return f"LCD-{self.lcd_id}"


@dataclass
class ChangedPolicy:
    policy_type: str  # 'ncd' | 'lcd'
    policy_id: str  # raw id (e.g. '220.4' or 'L33392')
    title: str
    last_modified: str | None
    document_url: str


# --------------------------------------------------------------------------- #
# Code extraction
# --------------------------------------------------------------------------- #
def extract_codes_from_text(text: str) -> list[str]:
    """CPT/HCPCS/ICD-10 code numbers referenced in ``text`` (deduped, ordered).

    These are facts present in the public-domain source document. DL-54: code
    numbers only — never AMA CPT descriptors.
    """
    if not text:
        return []
    seen: dict[str, None] = {}
    for rx in (_HCPCS_RE, _ICD10_RE, _CPT_RE):
        for m in rx.finditer(text):
            seen.setdefault(m.group(0), None)
    return list(seen.keys())


# --------------------------------------------------------------------------- #
# Parsing (pure — fixture-testable, no network)
# --------------------------------------------------------------------------- #
def _rows(payload: object) -> list[dict]:
    """Tolerate {'data':[...]}, {'results':[...]}, {'rows':[...]} or a bare list."""
    if isinstance(payload, dict):
        for key in ("data", "results", "rows", "items"):
            val = payload.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def _first(row: dict, *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return str(row[k])
    return None


def parse_ncd_index(payload: object) -> list[NcdSummary]:
    out: list[NcdSummary] = []
    for row in _rows(payload):
        ncd_id = _first(row, "ncd_id", "ncdid", "id", "NCD_ID")
        if not ncd_id:
            continue
        out.append(
            NcdSummary(
                ncd_id=ncd_id,
                title=_first(row, "title", "ncd_title", "name") or "",
                effective_date=_first(row, "effective_date", "eff_date", "effectiveDate"),
                last_modified=_first(
                    row, "last_modified", "updated", "lastModified", "revision_date"
                ),
                document_url=_first(row, "document_url", "url") or f"{NCD_DOC_URL}?ncdid={ncd_id}",
            )
        )
    return out


def parse_lcd_index(payload: object, state: str | None = None) -> list[LcdSummary]:
    out: list[LcdSummary] = []
    for row in _rows(payload):
        lcd_id = _first(row, "lcd_id", "lcdid", "id", "LCD_ID")
        if not lcd_id:
            continue
        st = _first(row, "state", "jurisdiction_state", "geo_state")
        if state and (st or "").upper() != state.upper():
            continue
        out.append(
            LcdSummary(
                lcd_id=lcd_id,
                title=_first(row, "title", "lcd_title", "name") or "",
                mac=_first(row, "mac", "contractor", "contractor_name", "mac_name"),
                state=st,
                effective_date=_first(row, "effective_date", "eff_date", "effectiveDate"),
                last_modified=_first(
                    row, "last_modified", "updated", "lastModified", "revision_date"
                ),
                document_url=_first(row, "document_url", "url") or f"{LCD_DOC_URL}?lcdid={lcd_id}",
            )
        )
    return out


class _SectionHTMLParser(HTMLParser):
    """Split an MCD document body into (heading, body) sections.

    Headings are h1–h4 (or elements with a 'section'/'field-label' class); body is
    the text accumulated until the next heading. Coarse but dependency-free.
    """

    _HEADINGS = {"h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[tuple[str, str]] = []
        self._cur_heading = ""
        self._buf: list[str] = []
        self._in_heading = False
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._HEADINGS:
            self._flush()
            self._in_heading = True
            self._heading_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._HEADINGS and self._in_heading:
            self._cur_heading = " ".join("".join(self._heading_buf).split())
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_buf.append(data)
        else:
            self._buf.append(data)

    def _flush(self) -> None:
        body = " ".join("".join(self._buf).split())
        if self._cur_heading or body:
            self.sections.append((self._cur_heading or "General", body))
        self._buf = []
        self._cur_heading = ""

    def close(self) -> None:  # type: ignore[override]
        super().close()
        self._flush()


def parse_sections_from_html(html: str) -> list[PolicySection]:
    p = _SectionHTMLParser()
    p.feed(html)
    p.close()
    out: list[PolicySection] = []
    for i, (heading, body) in enumerate(p.sections, start=1):
        if not body.strip():
            continue
        out.append(
            PolicySection(
                heading=heading,
                body=body,
                applicable_codes=extract_codes_from_text(f"{heading} {body}"),
                section_number=str(i),
            )
        )
    return out


def _sections_from_json(doc: dict) -> list[PolicySection]:
    raw = doc.get("sections")
    if not isinstance(raw, list):
        return []
    out: list[PolicySection] = []
    for i, s in enumerate(raw, start=1):
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading", "") or "General")
        body = str(s.get("body", "") or "")
        codes = s.get("applicable_codes")
        if not isinstance(codes, list):
            codes = extract_codes_from_text(f"{heading} {body}")
        out.append(
            PolicySection(
                heading=heading,
                body=body,
                applicable_codes=[str(c) for c in codes],
                section_number=str(s.get("section_number", i)),
            )
        )
    return out


def parse_ncd_document(payload: object, ncd_id: str) -> NcdDocument:
    """Parse an NCD document. Accepts a JSON dict (with 'sections' or 'full_text'/
    'body_html') or a raw HTML string."""
    if isinstance(payload, dict):
        sections = _sections_from_json(payload)
        if not sections and payload.get("body_html"):
            sections = parse_sections_from_html(str(payload["body_html"]))
        full_text = str(payload.get("full_text") or " ".join(s.body for s in sections))
        return NcdDocument(
            ncd_id=str(payload.get("ncd_id", ncd_id)),
            title=str(payload.get("title", "")),
            full_text=full_text,
            sections=sections,
            effective_date=_first(payload, "effective_date", "effectiveDate"),
            last_modified=_first(payload, "last_modified", "lastModified"),
            parent_part=_first(payload, "part"),
            parent_subpart=_first(payload, "subpart"),
        )
    sections = parse_sections_from_html(str(payload))
    return NcdDocument(
        ncd_id=ncd_id,
        title="",
        full_text=" ".join(s.body for s in sections),
        sections=sections,
    )


def parse_lcd_document(payload: object, lcd_id: str) -> LcdDocument:
    if isinstance(payload, dict):
        sections = _sections_from_json(payload)
        if not sections and payload.get("body_html"):
            sections = parse_sections_from_html(str(payload["body_html"]))
        full_text = str(payload.get("full_text") or " ".join(s.body for s in sections))
        return LcdDocument(
            lcd_id=str(payload.get("lcd_id", lcd_id)),
            title=str(payload.get("title", "")),
            mac=_first(payload, "mac", "contractor", "contractor_name"),
            state=_first(payload, "state"),
            full_text=full_text,
            sections=sections,
            effective_date=_first(payload, "effective_date", "effectiveDate"),
            last_modified=_first(payload, "last_modified", "lastModified"),
            parent_part=_first(payload, "part"),
            parent_subpart=_first(payload, "subpart"),
        )
    sections = parse_sections_from_html(str(payload))
    return LcdDocument(
        lcd_id=lcd_id,
        title="",
        mac=None,
        state=None,
        full_text=" ".join(s.body for s in sections),
        sections=sections,
    )


# --------------------------------------------------------------------------- #
# Diff
# --------------------------------------------------------------------------- #
def _aware(dt: datetime.datetime) -> datetime.datetime:
    """Coerce a possibly-naive datetime to UTC-aware (CMS strings are naive; the
    cms_ingestion_state timestamps are tz-aware — normalize before comparing)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=datetime.timezone.utc)


def _parse_dt(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return _aware(datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        try:
            return _aware(datetime.datetime.fromisoformat(str(value)[:10]))
        except ValueError:
            return None


def diff_since(
    last_indexed: dict[str, datetime.datetime],
    current: list[NcdSummary | LcdSummary] | None = None,
) -> list[ChangedPolicy]:
    """Return only policies added or updated since their per-id last-indexed time.

    ``last_indexed`` maps raw policy id -> last-indexed datetime. ``current`` is the
    current index (NcdSummary/LcdSummary). Passing ``current`` keeps this pure +
    testable; callers that omit it must fetch the index themselves first.
    """
    changed: list[ChangedPolicy] = []
    for s in current or []:
        is_ncd = isinstance(s, NcdSummary)
        raw_id = s.ncd_id if is_ncd else s.lcd_id  # type: ignore[union-attr]
        last = last_indexed.get(raw_id)
        modified = _parse_dt(s.last_modified) or _parse_dt(s.effective_date)
        if last is not None and modified is not None and modified <= _aware(last):
            continue  # unchanged since last index
        changed.append(
            ChangedPolicy(
                policy_type="ncd" if is_ncd else "lcd",
                policy_id=raw_id,
                title=s.title,
                last_modified=s.last_modified,
                document_url=s.document_url,
            )
        )
    return changed


# --------------------------------------------------------------------------- #
# Fetch (network — throttled + robots-aware)
# --------------------------------------------------------------------------- #
_robots: RobotFileParser | None = None


def _robots_ok(url: str) -> bool:
    global _robots
    try:
        if _robots is None:
            _robots = RobotFileParser()
            _robots.set_url(f"{MCD_BASE}/robots.txt")
            _robots.read()
        return _robots.can_fetch(_USER_AGENT, url)
    except Exception:  # noqa: BLE001 — robots unreachable -> be permissive but proceed throttled
        return True


async def _get(url: str, params: dict | None = None) -> httpx.Response:
    if not _robots_ok(url):
        raise PermissionError(f"robots.txt disallows fetching {url}")
    async with _sema:
        await asyncio.sleep(_THROTTLE_SECONDS)
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as c:
            resp = await c.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            return resp


async def fetch_ncd_index() -> list[NcdSummary]:
    resp = await _get(NCD_INDEX_URL)
    return parse_ncd_index(resp.json())


async def fetch_lcd_index(state: str | None = None) -> list[LcdSummary]:
    params = {"state": state} if state else None
    resp = await _get(LCD_INDEX_URL, params=params)
    return parse_lcd_index(resp.json(), state=state)


async def fetch_ncd_document(ncd_id: str) -> NcdDocument:
    resp = await _get(NCD_DOC_URL, params={"ncdid": ncd_id})
    ctype = resp.headers.get("content-type", "")
    payload: object = resp.json() if "json" in ctype else resp.text
    return parse_ncd_document(payload, ncd_id)


async def fetch_lcd_document(lcd_id: str) -> LcdDocument:
    resp = await _get(LCD_DOC_URL, params={"lcdid": lcd_id})
    ctype = resp.headers.get("content-type", "")
    payload: object = resp.json() if "json" in ctype else resp.text
    return parse_lcd_document(payload, lcd_id)
