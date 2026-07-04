"""PHI log scrubbing — regex default + nested-value coverage + Presidio flag.

The regex path is always exercised. The Presidio path is skipped when presidio /
its spaCy model isn't importable in the sandbox (guarded).
"""

from __future__ import annotations

import importlib

import pytest

from app.config import get_settings
from app.middleware import phi_log_filter as plf


def test_regex_scrub_redacts_ssn_and_email(monkeypatch):
    monkeypatch.setattr(get_settings(), "use_real_presidio", False)
    out = plf.scrub("patient 123-45-6789 email jane@example.com")
    assert "123-45-6789" not in out
    assert "jane@example.com" not in out
    assert "[REDACTED]" in out


def test_scrub_event_handles_nested_values(monkeypatch):
    monkeypatch.setattr(get_settings(), "use_real_presidio", False)
    event = {
        "msg": "ssn 123-45-6789",
        "meta": {"contact": {"email": "jane@example.com"}, "notes": ["MRN 12345678", 42]},
        "count": 7,
    }
    out = plf.scrub_event(None, "info", event)
    assert "123-45-6789" not in out["msg"]
    assert "jane@example.com" not in out["meta"]["contact"]["email"]
    assert "12345678" not in out["meta"]["notes"][0]
    # Non-strings pass through untouched.
    assert out["meta"]["notes"][1] == 42
    assert out["count"] == 7


def _presidio_available() -> bool:
    try:
        importlib.import_module("presidio_analyzer")
        importlib.import_module("presidio_anonymizer")
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _presidio_available(), reason="presidio not installed in sandbox")
def test_presidio_scrub_when_flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "use_real_presidio", True)
    # Presidio recognizes person names / emails the coarse regex would miss.
    out = plf.scrub("Contact John Smith at john.smith@example.com")
    assert "john.smith@example.com" not in out


def test_presidio_failure_falls_back_to_regex(monkeypatch):
    # Flag on but Presidio engines unavailable → must NOT raise; regex still scrubs.
    monkeypatch.setattr(get_settings(), "use_real_presidio", True)
    monkeypatch.setattr(plf, "_presidio_engines", lambda: None)
    out = plf.scrub("ssn 123-45-6789")
    assert "123-45-6789" not in out
    assert "[REDACTED]" in out
