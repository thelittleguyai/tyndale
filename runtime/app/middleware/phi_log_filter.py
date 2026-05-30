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


def scrub(text: str) -> str:
    """Redact coarse PHI patterns from a string."""
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


def scrub_event(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor — scrub every string value in the event dict before
    it is rendered/shipped to Azure Monitor."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = scrub(value)
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
