"""In-memory last-Claude-call health, for admin diagnosability (no secrets).

Records the outcome of the most recent Claude call — ok/error, a UTC timestamp, the
routing path, and a SHORT label (an exception class name, never the raw message or any
token/secret). Read by the admin System endpoint; written by the chat + audit paths and
by scripts/foundry_smoke.py. Deliberately tiny + dependency-free — this is observability,
NOT the encrypted audit log. State is per-replica (resets on restart), which is fine for a
"did the last Claude call work" health signal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

# The ONLY message a user ever sees when a Claude/provider call fails — the raw
# provider exception (auth/invalid_scope/etc.) is logged server-side + recorded via
# record_claude_call, never streamed to the user.
CLAUDE_UNAVAILABLE_MESSAGE = "Tyndale had trouble answering just now — please try again."


class ProviderUnavailableError(Exception):
    """A Claude/provider call failed. Carries ONLY the generic, user-safe message —
    never raw provider text. Raised by the audit path (and available to any caller) so
    nothing downstream renders the underlying exception."""

    def __init__(self, message: str = CLAUDE_UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


_lock = Lock()
_last: dict[str, str | None] = {"status": "unknown", "at": None, "path": None, "detail": None}


def record_claude_call(*, ok: bool, path: str, detail: str | None = None) -> None:
    """Record the outcome of a Claude call. ``detail`` MUST be a short, non-sensitive
    label (e.g. the exception class name) — never a raw provider message or token."""
    with _lock:
        _last["status"] = "ok" if ok else "error"
        _last["at"] = datetime.now(timezone.utc).isoformat()
        _last["path"] = path
        _last["detail"] = detail


def last_claude_call() -> dict[str, str | None]:
    """Snapshot of the last recorded Claude call (safe to serialize to admins)."""
    with _lock:
        return dict(_last)


# Item 1 — last real-agent audit run: duration, terminal reason, Stop-gate regenerations,
# and per-stage timings. Per-replica, resets on restart (an observability signal, not the
# audit log). Surfaced on the admin System page next to the Claude-call health.
_last_audit: dict = {
    "at": None,
    "duration_seconds": None,
    "reason": None,
    "regens": None,
    "path": None,
    "stage_ms": None,
}


def record_audit_run(
    *,
    duration_seconds: float,
    reason: str,
    regens: int,
    path: str,
    stage_ms: dict | None = None,
) -> None:
    """Record the most recent audit run's timing + outcome. ``reason`` is 'complete' or the
    incomplete reason (budget_exceeded | no_three_number_finding | error)."""
    with _lock:
        _last_audit.update(
            at=datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration_seconds,
            reason=reason,
            regens=regens,
            path=path,
            stage_ms=stage_ms or {},
        )


def last_audit_run() -> dict:
    """Snapshot of the last audit run's health (safe to serialize to admins)."""
    with _lock:
        return dict(_last_audit)


def claude_path_label(settings) -> str:
    """The active Claude routing path: 'foundry' | 'anthropic-direct' | 'stub'.

    Mirrors runner._client()'s precedence + the admin health check. Self-contained
    (no import of runner) to avoid a circular import with the recording call sites.
    """
    if settings.use_foundry and settings.foundry_endpoint:
        return "foundry"
    key = (settings.anthropic_api_key or "").strip()
    if settings.litellm_proxy_url or (key and not key.startswith("<") and key.startswith("sk-")):
        return "anthropic-direct"
    return "stub"
