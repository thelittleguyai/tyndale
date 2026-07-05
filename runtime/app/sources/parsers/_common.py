"""Shared, defensive text helpers for the document parsers (Sprint E).

Parsers work on OCR text whose layout varies, so everything here fails soft: a field that
can't be found returns None (never a fabricated 0.0 or guessed date). Money and dates are
normalized; callers attach per-field confidence.
"""

from __future__ import annotations

import re
from datetime import datetime

_MONEY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")
_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ("January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"),
        start=1,
    )
}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})


def money(token: str | None) -> float | None:
    """First dollar amount in ``token`` as a float, or None."""
    if not token:
        return None
    m = _MONEY_RE.search(token)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_date_token(token: str | None) -> str | None:
    """Normalize a date token to ISO (YYYY-MM-DD). Handles MM/DD/YYYY and 'Month D, YYYY'."""
    if not token:
        return None
    token = token.strip()
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", token)
    if m:
        mm, dd, yy = (int(x) for x in m.groups())
        if yy < 100:
            yy += 2000
        try:
            return datetime(yy, mm, dd).date().isoformat()
        except ValueError:
            return None
    m = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b", token)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            try:
                return datetime(int(m.group(3)), mon, int(m.group(2))).date().isoformat()
            except ValueError:
                return None
    return None


def _line_after_label(text: str, *labels: str) -> str | None:
    """The remainder of the line following the first matching label (case-insensitive)."""
    lowered = text.lower()
    for label in labels:
        idx = lowered.find(label.lower())
        if idx != -1:
            start = idx + len(label)
            end = text.find("\n", start)
            return text[start : end if end != -1 else len(text)]
    return None


def money_after(text: str, *labels: str) -> float | None:
    """The first dollar amount on the line that carries one of ``labels``."""
    return money(_line_after_label(text, *labels))


def date_after(text: str, *labels: str) -> str | None:
    """The first date on the line that carries one of ``labels`` (ISO), else None."""
    return parse_date_token(_line_after_label(text, *labels))


def text_after(text: str, *labels: str) -> str | None:
    """The trimmed remainder of the line after a label (e.g. a provider name)."""
    line = _line_after_label(text, *labels)
    if line is None:
        return None
    cleaned = line.strip(" :\t-")
    return cleaned or None
