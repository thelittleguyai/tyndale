"""Bounded backoff for every Claude call on the audit path (e2e re-test 2026-09-23, item 1).

The specimen audit (f6e5c56d) persisted three findings and then died on ONE ``RateLimitError``
from the Foundry deployment on the Lead Planner's summary call — the SDK's own two quick
retries (0.5 s → 8 s) were spent inside a single throttling window, the exception escaped
``run_agent`` as ``ProviderUnavailableError`` and the whole run ended ``system_error``.

Every ``messages.create`` the orchestrator makes (Bill Detective, Math Person, the Lead
Planner, translate mode) goes through ``create_message`` here:

  * up to ``MAX_ATTEMPTS`` calls, waiting 2 → 4 → 8 s (capped at ``MAX_DELAY_S``) between
    them — or longer when the provider says so: ``retry-after-ms`` / ``retry-after`` is
    honoured up to ``MAX_RETRY_AFTER_S``. A provider asking for more than that is not a
    transient blip we should sit inside an audit waiting out;
  * never past the audit's wall-clock budget — a wait the budget cannot afford is not
    taken, the error is raised at once and the caller degrades;
  * only for errors a wait can fix: 429, 5xx (529 "overloaded" included), connection
    errors and timeouts. A 400 / 401 / 403 / 404 is raised on the first attempt;
  * the SDK's own retries are switched OFF for these calls (``max_retries=0``) so the policy
    is this module's alone and the worst case is bounded and known.

Every throttled attempt is recorded in ``llm_health`` (the admin System page reads it) and
logged as ``claude.retry``.

``FAULT`` is the dev-only fault seam the e2e harness drives (see ``app.faults``): while it is
set, the call raises a synthesized 429 instead of reaching the provider, so the retry path and
everything downstream of it run exactly as they would against a throttled deployment.
"""

from __future__ import annotations

import asyncio
import email.utils
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

import structlog

from app.agents.audit_budget import current_audit_budget

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 4
BASE_DELAY_S = 2.0
MAX_DELAY_S = 16.0
MAX_RETRY_AFTER_S = 60.0
# A wait is only taken when the audit budget can still afford it with this much to spare.
BUDGET_MARGIN_S = 5.0

# "rate_limit" while an injected 429 is in force (dev e2e only — app.faults decides when).
FAULT: ContextVar[str | None] = ContextVar("claude_fault", default=None)
_FAULT_RETRY_AFTER_S = 1


def _retryable_errors() -> tuple[type[BaseException], ...]:
    import anthropic

    # APITimeoutError subclasses APIConnectionError; 529 "overloaded" is an InternalServerError.
    return (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)


def _headers(exc: BaseException):
    response = getattr(exc, "response", None)
    return getattr(response, "headers", None) or {}


def retry_after_seconds(exc: BaseException) -> float | None:
    """The provider's own wait hint: ``retry-after-ms`` (milliseconds), else ``retry-after``
    (seconds, or an HTTP date). None when absent or unparseable."""
    headers = _headers(exc)
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return max(0.0, float(ms) / 1000.0)
        except ValueError:
            pass
    ra = headers.get("retry-after")
    if not ra:
        return None
    try:
        return max(0.0, float(ra))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(ra)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    return max(0.0, when.timestamp() - time.time())


def backoff_delay(attempt: int, retry_after: float | None) -> float:
    """The wait after failed attempt ``attempt`` (1-based): exponential from BASE_DELAY_S,
    capped at MAX_DELAY_S — or the provider's hint when it asks for longer."""
    delay = min(BASE_DELAY_S * (2 ** (attempt - 1)), MAX_DELAY_S)
    if retry_after is not None:
        delay = max(delay, retry_after)
    return delay


def status_of(exc: BaseException) -> int | None:
    return getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)


def _simulated_rate_limit():
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://fault-injection.invalid/v1/messages")
    response = httpx.Response(429, headers={"retry-after": str(_FAULT_RETRY_AFTER_S)}, request=request)
    return anthropic.RateLimitError("injected 429 (dev e2e fault)", response=response, body=None)


async def create_message(
    client: Any,
    *,
    actor: str,
    case_file_id: str | None = None,
    path: str | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    **kwargs: Any,
) -> Any:
    """``client.messages.create(**kwargs)`` under the bounded backoff above. Raises the last
    provider error once the attempts, the provider's patience or the audit budget run out."""
    from app.agents.llm_health import record_rate_limit

    retryable = _retryable_errors()
    if hasattr(client, "with_options"):
        client = client.with_options(max_retries=0)
    attempt = 0
    while True:
        attempt += 1
        try:
            if FAULT.get() == "rate_limit":
                raise _simulated_rate_limit()
            return await client.messages.create(**kwargs)
        except retryable as exc:
            status = status_of(exc)
            hint = retry_after_seconds(exc)
            if status == 429:
                record_rate_limit(path=path, retry_after=hint, headers=_headers(exc))
            if attempt >= MAX_ATTEMPTS:
                log.warning(
                    "claude.retry.exhausted", actor=actor, case_file_id=case_file_id,
                    attempts=attempt, status=status, error_class=type(exc).__name__,
                )
                raise
            delay = backoff_delay(attempt, hint)
            budget = current_audit_budget()
            affordable = budget is None or delay + BUDGET_MARGIN_S < budget.remaining_seconds()
            if delay > MAX_RETRY_AFTER_S or not affordable:
                log.warning(
                    "claude.retry.abandoned", actor=actor, case_file_id=case_file_id,
                    attempts=attempt, status=status, wait_s=round(delay, 1),
                    reason="provider_wait_too_long" if delay > MAX_RETRY_AFTER_S else "audit_budget",
                )
                raise
            log.warning(
                "claude.retry", actor=actor, case_file_id=case_file_id, attempt=attempt,
                status=status, error_class=type(exc).__name__, wait_s=round(delay, 1),
                retry_after=hint,
            )
            await sleep(delay)
