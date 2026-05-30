"""Claude-driven structured extraction of NCD/LCD coverage rules (Phase CO-2A).

extract_policy() pulls structured fields (applicable codes, covered/excluded
conditions, prior-auth, frequency limits, documentation requirements, effective
dates, revision history) from a parsed NCD/LCD document.

Two paths, mirroring the orchestrator's Phase-2D discipline:
  - real Claude (use_real_claude + creds): a JSON-only structured-output prompt
    via the existing Anthropic client (LiteLLM proxy honored), parsed with
    reject-and-retry on malformed output (the Phase-2I structured-extraction
    pattern).
  - stub (default in dev/CI/tests): a deterministic extraction derived from the
    document so the pipeline + tests run with no ANTHROPIC_API_KEY.

DL-54: we extract code NUMBERS (facts in the public-domain source). We never ask
for, store, or emit AMA CPT descriptors — those await license clearance.
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import asdict, dataclass, field

import structlog

from app.config import get_settings
from app.ingestion.cms_ncd_lcd import LcdDocument, NcdDocument, extract_codes_from_text

log = structlog.get_logger(__name__)

_MAX_RETRIES = 3


@dataclass
class ExtractedPolicy:
    applicable_codes: list[str] = field(default_factory=list)
    covered_conditions: list[str] = field(default_factory=list)
    excluded_conditions: list[str] = field(default_factory=list)
    prior_authorization_required: bool | None = None
    frequency_limits: dict = field(default_factory=dict)
    documentation_requirements: list[str] = field(default_factory=list)
    effective_date_start: datetime.date | None = None
    effective_date_end: datetime.date | None = None
    revision_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["effective_date_start"] = (
            self.effective_date_start.isoformat() if self.effective_date_start else None
        )
        d["effective_date_end"] = (
            self.effective_date_end.isoformat() if self.effective_date_end else None
        )
        return d


def _use_real_claude() -> bool:
    s = get_settings()
    if not s.use_real_claude:
        return False
    if s.litellm_proxy_url:
        return True
    return (s.anthropic_api_key or "").strip().startswith("sk-")


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


_FREQ_RE = re.compile(
    r"(once|one|1|two|2|three|3|four|4)\s+(?:time[s]?\s+)?per\s+(year|month|day|lifetime|beneficiary)",
    re.IGNORECASE,
)


def _stub_extract(document: NcdDocument | LcdDocument) -> ExtractedPolicy:
    """Deterministic extraction from the document — the no-real-Claude floor."""
    codes: list[str] = []
    for s in document.sections:
        for c in s.applicable_codes:
            if c not in codes:
                codes.append(c)
    for c in extract_codes_from_text(document.full_text):
        if c not in codes:
            codes.append(c)

    text = document.full_text.lower()
    prior_auth: bool | None = None
    if "prior authorization" in text or "prior auth" in text:
        prior_auth = True

    freq: dict = {}
    m = _FREQ_RE.search(document.full_text)
    if m:
        freq = {"raw": m.group(0), "period": m.group(2).lower()}

    doc_reqs: list[str] = [
        s.heading
        for s in document.sections
        if "document" in s.heading.lower() or "medical record" in s.body.lower()
    ]

    return ExtractedPolicy(
        applicable_codes=codes,
        covered_conditions=[],
        excluded_conditions=[],
        prior_authorization_required=prior_auth,
        frequency_limits=freq,
        documentation_requirements=doc_reqs,
        effective_date_start=_parse_date(document.effective_date),
        effective_date_end=None,
        revision_history=[],
    )


_SYSTEM = (
    "You extract structured coverage rules from public-domain Medicare NCD/LCD "
    "documents. Return ONLY a single JSON object, no prose, no code fences. "
    "Use code NUMBERS only (CPT/HCPCS/ICD-10) — NEVER write out AMA CPT long "
    "descriptors. If a field is unknown, use null / [] / {}."
)

_SCHEMA_HINT = (
    '{"applicable_codes": ["string"], "covered_conditions": ["string"], '
    '"excluded_conditions": ["string"], "prior_authorization_required": true|false|null, '
    '"frequency_limits": {"period": "year|month|...", "limit": "string"}, '
    '"documentation_requirements": ["string"], "effective_date_start": "YYYY-MM-DD|null", '
    '"effective_date_end": "YYYY-MM-DD|null", '
    '"revision_history": [{"date": "YYYY-MM-DD", "description": "string"}]}'
)


def _coerce(raw: dict, document: NcdDocument | LcdDocument) -> ExtractedPolicy:
    return ExtractedPolicy(
        applicable_codes=[str(c) for c in raw.get("applicable_codes") or []],
        covered_conditions=[str(c) for c in raw.get("covered_conditions") or []],
        excluded_conditions=[str(c) for c in raw.get("excluded_conditions") or []],
        prior_authorization_required=raw.get("prior_authorization_required"),
        frequency_limits=raw.get("frequency_limits") or {},
        documentation_requirements=[str(c) for c in raw.get("documentation_requirements") or []],
        effective_date_start=_parse_date(raw.get("effective_date_start"))
        or _parse_date(document.effective_date),
        effective_date_end=_parse_date(raw.get("effective_date_end")),
        revision_history=[r for r in raw.get("revision_history") or [] if isinstance(r, dict)],
    )


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t.strip()


async def extract_policy(document: NcdDocument | LcdDocument) -> ExtractedPolicy:
    """Structured extraction. Stubs deterministically unless real Claude is wired."""
    if not _use_real_claude():
        return _stub_extract(document)

    from app.agents.runner import _client  # reuse the configured Anthropic/LiteLLM client

    client = _client()
    model = get_settings().claude_default_model_sonnet
    sections_text = (
        "\n\n".join(f"## {s.heading}\n{s.body}" for s in document.sections) or document.full_text
    )
    user_msg = (
        f"Document title: {document.title}\n"
        f"Effective date (if known): {document.effective_date}\n\n"
        f"Extract structured fields matching this JSON shape:\n{_SCHEMA_HINT}\n\n"
        f"Document sections:\n{sections_text[:60000]}"
    )

    last_err: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        resp = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        try:
            raw = json.loads(_strip_fences(text))
            if not isinstance(raw, dict):
                raise ValueError("expected a JSON object")
            return _coerce(raw, document)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            log.warning("extract_policy.malformed_json", attempt=attempt, error=str(e))
            user_msg += (
                "\n\nYour previous reply was not valid JSON. Reply with ONLY the JSON object."
            )

    log.error("extract_policy.giving_up", error=str(last_err))
    # Fall back to the deterministic floor rather than failing the whole ingestion.
    return _stub_extract(document)
