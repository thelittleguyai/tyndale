"""Retrieval health — the in-process ledger the System page and the audit read (e2e 2026-09-23 B1).

Retrieval was dead on dev for days (Voyage 429 on embeddings, a deterministic 400 on rerank)
and nothing said so: Qdrant reported healthy, every knowledge tool errored, and the sweep
stayed green. Every Voyage call and every knowledge-tool call now lands here, so:

  * ``snapshot()`` gives the System page a ``retrieval_degraded`` signal — the last-N
    knowledge-tool error rate plus the last Voyage failure by endpoint and status;
  * the same counters feed the structured ``retrieval.degraded`` log line ops can alert on.

Per process, best-effort, never raises. The durable per-case record is the audit-event
ledger (``tool_invocation`` rows) — this is the live view.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone

import structlog

log = structlog.get_logger(__name__)

# Last-N knowledge-tool outcomes (True = ok). N is small on purpose: the signal should flip
# within one audit, not after a day of history.
WINDOW = 50
DEGRADED_ERROR_RATE = 0.2  # ≥ 1 in 5 recent knowledge-tool calls failing → degraded

_lock = threading.Lock()
_tool_outcomes: deque[bool] = deque(maxlen=WINDOW)
_voyage: dict[str, dict] = {}  # endpoint -> {last_status, last_error, last_error_at, last_ok_at, errors}
_state = {"last_alert_at": None}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_tool_call(tool: str, ok: bool, error: str | None = None) -> None:
    """One knowledge-tool call (qdrant_search_*). Logs the degraded transition once per
    flip so a Log Analytics alert can key on ``retrieval.degraded``."""
    with _lock:
        was = _degraded_locked()
        _tool_outcomes.append(ok)
        now_degraded = _degraded_locked()
    if ok:
        return
    log.warning("knowledge.tool_failed", tool=tool, error=(error or "")[:200])
    if now_degraded and not was:
        with _lock:
            _state["last_alert_at"] = _now()
        snap = snapshot()
        log.error(
            "retrieval.degraded",
            window_calls=snap["window_calls"],
            window_errors=snap["window_errors"],
            error_rate=snap["error_rate"],
            voyage=snap["voyage"],
        )


def record_voyage(endpoint: str, ok: bool, status: int | None = None, error: str | None = None) -> None:
    """One Voyage HTTP outcome (``embeddings`` | ``contextualizedembeddings`` | ``rerank``)."""
    with _lock:
        entry = _voyage.setdefault(
            endpoint,
            {"last_status": None, "last_error": None, "last_error_at": None, "last_ok_at": None, "errors": 0},
        )
        entry["last_status"] = status
        if ok:
            entry["last_ok_at"] = _now()
        else:
            entry["errors"] = int(entry["errors"]) + 1
            entry["last_error"] = (error or "")[:200]
            entry["last_error_at"] = _now()


def _degraded_locked() -> bool:
    n = len(_tool_outcomes)
    if n == 0:
        return False
    errors = sum(1 for ok in _tool_outcomes if not ok)
    return errors / n >= DEGRADED_ERROR_RATE


def snapshot() -> dict:
    """The System-page block. ``status``: healthy | degraded | unknown (no calls yet)."""
    with _lock:
        n = len(_tool_outcomes)
        errors = sum(1 for ok in _tool_outcomes if not ok)
        voyage = {k: dict(v) for k, v in _voyage.items()}
        last_alert_at = _state["last_alert_at"]
    if n == 0:
        status = "unknown"
    elif errors / n >= DEGRADED_ERROR_RATE:
        status = "degraded"
    else:
        status = "healthy"
    return {
        "status": status,
        "window": WINDOW,
        "window_calls": n,
        "window_errors": errors,
        "error_rate": round(errors / n, 3) if n else 0.0,
        "voyage": voyage,
        "last_alert_at": last_alert_at,
    }


def reset() -> None:
    """Tests only."""
    with _lock:
        _tool_outcomes.clear()
        _voyage.clear()
        _state["last_alert_at"] = None
