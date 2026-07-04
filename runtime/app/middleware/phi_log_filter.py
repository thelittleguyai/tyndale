"""Coarse PHI-pattern scrubbing for application logs (Phase 2K.2 / DL-46).

This is a BRIDGE measure. Real PHI scrubbing in Phase 4 uses Microsoft Presidio
+ custom recognizers (the security/HIPAA contact's work; see
docs/integration-contracts.md §2.1 PreToolUse hook). Coverage here is
intentionally conservative — false positives (redacting non-PHI) are preferred
over false negatives (leaking real PHI).

Applied to the standard application log (structlog → console) via the
``scrub_event`` processor wired in app/main.py, NOT to the audit log (which goes
to Postgres, encrypted). ``PHILogFilter`` is also provided for any stdlib
loggers (e.g. uvicorn access logs).
"""

from __future__ import annotations

import logging
import re
from typing import Any

_REDACTED = "[REDACTED]"

# Coarse, conservative regexes. Apply more-specific patterns first.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN: 123-45-6789
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),  # email
    re.compile(r"\bMRN[:#\s-]*\d{5,12}\b", re.IGNORECASE),  # MRN-like
    re.compile(r"\b[A-Z]{2,4}\d{7,12}\b"),  # payer member IDs (UHC/Anthem-style alnum)
    # A dollar amount sitting next to a bill/claim/account identifier.
    re.compile(
        r"\$\d[\d,]*(?:\.\d{2})?[^\n]{0,20}\b(?:claim|acct|account|invoice|inv|bill|member)\b[\s#:]*\w*",
        re.IGNORECASE,
    ),
]


def _regex_scrub(text: str) -> str:
    """Redact coarse PHI patterns from a string (the fast default path)."""
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


# Lazily-built Presidio engines (analyzer + anonymizer). Cached across calls so the
# spaCy model isn't reloaded per log line. None until first use / on import failure.
_PRESIDIO: tuple[Any, Any] | None = None
_PRESIDIO_FAILED = False


def _presidio_engines() -> tuple[Any, Any] | None:
    """Build (analyzer, anonymizer) once, or None if Presidio can't be imported /
    initialized (so the caller falls back to the regex scrub)."""
    global _PRESIDIO, _PRESIDIO_FAILED
    if _PRESIDIO is not None:
        return _PRESIDIO
    if _PRESIDIO_FAILED:
        return None
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _PRESIDIO = (AnalyzerEngine(), AnonymizerEngine())
        return _PRESIDIO
    except Exception:  # noqa: BLE001 — missing model/lib → regex fallback
        _PRESIDIO_FAILED = True
        return None


def _presidio_scrub(text: str) -> str:
    """Run Presidio analyze+anonymize over ``text``. Raises on any failure so the
    caller can fall back to the regex scrub."""
    engines = _presidio_engines()
    if engines is None:
        raise RuntimeError("presidio unavailable")
    analyzer, anonymizer = engines
    results = analyzer.analyze(text=text, language="en")
    if not results:
        return text
    return anonymizer.anonymize(text=text, analyzer_results=results).text


def scrub(text: str) -> str:
    """Redact PHI from a string. Uses Presidio when ``use_real_presidio`` is set
    (analyze+anonymize; imported lazily so it isn't loaded when off), else the fast
    regex path. Failure-safe: any Presidio import/analyze error falls back to regex."""
    from app.config import get_settings

    if get_settings().use_real_presidio:
        try:
            return _presidio_scrub(text)
        except Exception:  # noqa: BLE001 — never break logging; degrade to regex
            return _regex_scrub(text)
    return _regex_scrub(text)


def _scrub_value(value: Any) -> Any:
    """Recursively scrub PHI from any value type — top-level strings AND strings
    nested inside dicts / lists / tuples (the coarse regex path only reached
    top-level strings before)."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(v) for v in value)
    return value


def scrub_event(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor — scrub PHI from every value in the event dict (all
    types, nested) before it is rendered/shipped to Azure Monitor."""
    for key, value in list(event_dict.items()):
        event_dict[key] = _scrub_value(value)
    return event_dict


class PHILogFilter(logging.Filter):
    """stdlib logging.Filter for non-structlog loggers (uvicorn, etc.)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = scrub(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(scrub(a) if isinstance(a, str) else a for a in record.args)
        except Exception:  # noqa: BLE001 — a log filter must never break logging
            pass
        return True
