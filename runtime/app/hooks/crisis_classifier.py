"""Crisis classifier (DL-04 Category-2 gate).

Screens the user's latest chat message for imminent self-harm / suicidal-crisis /
medical-emergency intent BEFORE any normal processing. A positive signal triggers
the Category-2 clean decline (refusals.md: no 988, no routing), bypassing the Lead
Planner (the wiring lives in app/agents/chat.py).

Two layers, in priority order:

  1. A fast Haiku classification call (the same client factory the rest of the
     runtime uses — app.agents.runner._client — and the Haiku deployment resolved
     through config). Gated by ``use_real_crisis_classifier`` (default true) AND a
     usable LLM path (real creds / Foundry managed identity).
  2. A deterministic keyword screen. This is the FAILURE-SAFE fallback: on ANY
     classifier error, timeout, missing creds, or the flag being off, we fall back
     to the keyword screen rather than failing open silently. Per refusals.md,
     false positives are acceptable, false negatives are not.

The public ``crisis_classifier`` stays SYNCHRONOUS (the contract the chat ingress
calls). It runs the async Haiku path on a private event loop when possible; if it
is already inside a running loop (the streaming chat turn), it uses the async entry
point ``crisis_classifier_async`` instead — see chat.py.
"""

from __future__ import annotations

import asyncio
import re

import structlog

from app.config import get_settings
from app.hooks.contracts import CrisisClassifierInput, CrisisClassifierResult

log = structlog.get_logger(__name__)

# Deterministic keyword screen — the failure-safe floor. Conservative by design
# (refusals.md: prefer a false positive to a false negative). Word-boundary matched
# so "assist" doesn't trip "suicide" etc.
_CRISIS_TERMS: tuple[str, ...] = (
    "suicide",
    "suicidal",
    "kill myself",
    "kill my self",
    "end my life",
    "end it all",
    "take my life",
    "hurt myself",
    "harm myself",
    "self-harm",
    "self harm",
    "cut myself",
    "overdose",
    "want to die",
    "don't want to be here",
    "dont want to be here",
    "don't want to live",
    "dont want to live",
    "no reason to live",
    "better off dead",
)

_CRISIS_RE = re.compile(
    "|".join(re.escape(term) for term in _CRISIS_TERMS),
    re.IGNORECASE,
)

# Haiku classifier prompt. Binary output only — cheap + deterministic to parse.
_CLASSIFIER_SYSTEM = (
    "You are a safety classifier for a medical-billing assistant. Decide whether "
    "the user's message expresses IMMINENT self-harm, suicidal crisis, intent to "
    "harm themselves, or a life-threatening medical emergency. Err toward YES on "
    "borderline mental-health-crisis messages (a false positive is acceptable; a "
    "false negative is not). Do NOT flag ordinary frustration, anger at a bill, or "
    "figurative language (e.g. 'this bill is killing me'). Respond with EXACTLY one "
    "word: YES or NO."
)


def _keyword_screen(text: str) -> bool:
    """Deterministic crisis screen — the failure-safe fallback."""
    return bool(_CRISIS_RE.search(text or ""))


def _real_classifier_enabled() -> bool:
    """True when the Haiku classifier should be attempted: the flag is on AND there
    is a usable LLM path (real Anthropic creds or Foundry managed identity)."""
    settings = get_settings()
    if not getattr(settings, "use_real_crisis_classifier", True):
        return False
    # Lazy import — mirrors runner's creds gate so a placeholder/empty key degrades
    # to the keyword screen instead of hitting the API with an invalid key.
    from app.agents.runner import has_real_anthropic_creds

    return has_real_anthropic_creds(settings)


async def _haiku_detects_crisis(raw_message: str) -> bool:
    """One fast Haiku call. Raises on any transport/parse error so the caller can
    fall back to the keyword screen."""
    from app.agents.runner import _client

    settings = get_settings()
    model = settings.resolved_model(settings.claude_default_model_haiku)
    client = _client()

    # Hard timeout so a slow classifier never stalls chat ingress.
    resp = await asyncio.wait_for(
        client.messages.create(
            model=model,
            max_tokens=4,
            system=_CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content": raw_message}],
        ),
        timeout=5.0,
    )
    text = "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
    ).strip().upper()
    return text.startswith("YES")


async def crisis_classifier_async(inp: CrisisClassifierInput) -> CrisisClassifierResult:
    """Async crisis screen (used from the async chat ingress).

    Tries the Haiku classifier when enabled; on ANY error/timeout/missing-creds
    falls back to the deterministic keyword screen (logged). Never fails open."""
    keyword_hit = _keyword_screen(inp.raw_message)

    if not _real_classifier_enabled():
        return CrisisClassifierResult(crisis_detected=keyword_hit)

    try:
        detected = await _haiku_detects_crisis(inp.raw_message)
        # Belt-and-braces: if the keyword screen fires but Haiku says NO, honor the
        # keyword screen (false negatives are unacceptable per refusals.md).
        return CrisisClassifierResult(crisis_detected=bool(detected) or keyword_hit)
    except Exception as exc:  # noqa: BLE001 — safety path must never crash ingress
        log.warning(
            "crisis_classifier.fallback_keyword",
            error=str(exc),
            keyword_hit=keyword_hit,
        )
        return CrisisClassifierResult(crisis_detected=keyword_hit)


def crisis_classifier(inp: CrisisClassifierInput) -> CrisisClassifierResult:
    """Synchronous crisis screen (the CrisisClassifier contract shape).

    When called OUTSIDE a running event loop, it drives the async Haiku path on a
    private loop. When called from INSIDE a running loop (which cannot be nested),
    it cannot await the LLM, so it returns the deterministic keyword screen — the
    async chat ingress should call ``crisis_classifier_async`` to get the Haiku
    layer. Either way it never fails open."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to drive the async path to completion.
        return asyncio.run(crisis_classifier_async(inp))
    # Inside a running loop: fall back to the deterministic screen synchronously.
    return CrisisClassifierResult(crisis_detected=_keyword_screen(inp.raw_message))
