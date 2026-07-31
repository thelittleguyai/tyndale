"""The two chat declines (Brock §A2 state 4 / script §10).

Both are case-mode chat INGRESS behaviors, downstream of the existing hooks — the crisis
classifier's precedence is untouched (it runs first and returns before anything here).

    fabrication — the user asks Tyndale to exaggerate or misstate ("say it was an emergency").
                  Warm decline + a TRUTHFUL REFRAME: never a lecture, never a dead end. The
                  reframe pivots to the strongest REAL finding on the case, so the user leaves
                  with what is actually strong in their position.
    guarantee   — the user demands a win prediction ("will I win?"). No prediction, ever
                  ([C] doctrine). The honest trio: a cited base rate where the corpus has one,
                  the strength-of-basis for THIS case, and a concrete next step.

Detection follows the verification_mapper pattern: deterministic phrases first (fast, free,
predictable), Haiku only when the deterministic pass is silent and real Claude is configured.
Detection FAILS OPEN to None — a missed decline is a normal chat turn, never a false refusal.
"""

from __future__ import annotations

import json
import re

import structlog

from app.agents.context_loader import orchestration_step
from app.config import get_settings

log = structlog.get_logger(__name__)

FABRICATION = "fabrication"
GUARANTEE = "guarantee"

# Deterministic first pass. Phrased tightly so ordinary billing talk never trips them —
# "was this an emergency?" is a question, "say it was an emergency" is a request to misstate.
_FABRICATION_PATTERNS = (
    r"\b(?:say|tell|write|put|claim|report|mark|make it look like)\b[^.?!]{0,40}\b(?:it|this|that|i|we|they)\b[^.?!]{0,40}\b(?:was|were|is|are|had|did)\b",
    r"\b(?:exaggerate|inflate|overstate|embellish|fudge|round up|pad)\b",
    r"\b(?:lie|lying|make (?:something|it|this) up|made up|fabricate|falsify)\b",
    r"\b(?:pretend|act like|hide|leave out|omit|don'?t mention)\b[^.?!]{0,40}\b(?:i|we|they|it|the)\b",
    r"\bcan (?:you|we) just say\b",
)
_GUARANTEE_PATTERNS = (
    r"\b(?:will|do|can) (?:i|we) (?:win|beat|get)\b[^.?!]{0,30}\b(?:this|it|the appeal|my money|refund)\b",
    r"\b(?:guarantee|promise|certain|sure thing|for sure)\b[^.?!]{0,30}\b(?:win|refund|money back|success|work)\b",
    r"\b(?:what are|whats|what's) (?:the|my) (?:odds|chances|likelihood|probability)\b",
    r"\bhow likely\b[^.?!]{0,30}\b(?:win|succeed|work|refund)\b",
    r"\b(?:am i|are we) going to win\b",
)

_FAB_RE = [re.compile(p, re.IGNORECASE) for p in _FABRICATION_PATTERNS]
_GUA_RE = [re.compile(p, re.IGNORECASE) for p in _GUARANTEE_PATTERNS]

_HAIKU_SYSTEM = (
    "You classify a single user message sent to a medical-billing advocate. Answer ONLY with a "
    'compact JSON object: {"intent":"fabrication|guarantee|none"}. '
    "fabrication = the user asks the assistant to say something untrue, exaggerate, inflate, or "
    "omit a fact to strengthen their case. guarantee = the user asks for a prediction, promise, "
    "odds, or guarantee about whether they will win/succeed. none = anything else, INCLUDING "
    "ordinary questions about their bill, their coverage, or what happens next. When unsure, "
    "answer none."
)


def detect_decline_deterministic(utterance: str) -> str | None:
    """Fast pass. Fabrication is checked first: a message that both misstates and asks about
    odds is foremost a request to fabricate."""
    if not utterance:
        return None
    if any(r.search(utterance) for r in _FAB_RE):
        return FABRICATION
    if any(r.search(utterance) for r in _GUA_RE):
        return GUARANTEE
    return None


def _haiku_enabled() -> bool:
    settings = get_settings()
    if not getattr(settings, "use_real_claude", False):
        return False
    from app.agents.runner import has_real_anthropic_creds

    return has_real_anthropic_creds(settings) or bool(settings.litellm_proxy_url)


async def _haiku_intent(utterance: str) -> str | None:
    from app.agents.runner import _client

    settings = get_settings()
    try:
        client = _client()
        resp = await client.messages.create(
            model=settings.resolved_model(settings.claude_default_model_haiku),
            max_tokens=32,
            system=_HAIKU_SYSTEM,
            messages=[{"role": "user", "content": utterance}],
        )
        raw = "".join(getattr(b, "text", "") for b in (resp.content or []))
        intent = (json.loads(raw).get("intent") or "").strip().lower()
        return intent if intent in (FABRICATION, GUARANTEE) else None
    except Exception as exc:  # noqa: BLE001 — a classifier failure is never a false refusal
        log.warning("declines.haiku_fallback", error=str(exc))
        return None


async def classify_decline(utterance: str) -> str | None:
    """The decline intent for a chat utterance, or None. Deterministic first; Haiku only when
    the deterministic pass is silent (and configured). Fails open to None."""
    hit = detect_decline_deterministic(utterance)
    if hit or not _haiku_enabled():
        return hit
    return await _haiku_intent(utterance)


def _strongest_finding(findings: list) -> object | None:
    """The most load-bearing REAL finding — ranked by the same dollar heuristic the gameplan
    uses (one ranking, not two)."""
    from app.sources.gameplan import _dollar_of

    actionable = [f for f in findings or [] if getattr(f, "status", "open") == "open"]
    if not actionable:
        return None
    return max(actionable, key=lambda f: (_dollar_of(f) or 0.0))


def fabrication_response(findings: list | None = None) -> str:
    """Warm decline + truthful reframe. The reframe names the strongest REAL finding, so the
    turn never dead-ends on a refusal — the honest version of their case IS the answer."""
    from app.sources.gameplan import _dollar_of, humanize_category

    text = orchestration_step("decline.fabrication")
    best = _strongest_finding(findings or [])
    if best is None:
        return text
    amount = _dollar_of(best)
    reframe = orchestration_step(
        "decline.fabrication_reframe",
        finding=humanize_category(getattr(best, "category", "") or ""),
        amount=f"{amount:,.2f}" if amount else "the amount in question",
    )
    return f"{text}\n\n{reframe}"


def guarantee_response(findings: list | None = None, *, base_rate: dict | None = None) -> str:
    """The honest trio — cited base rate where the corpus has one, strength-of-basis for THIS
    case, concrete next step. NEVER a probability for this case ([C] doctrine)."""
    from app.sources.gameplan import humanize_category

    best = _strongest_finding(findings or [])
    return orchestration_step(
        "decline.guarantee_trio",
        base_rate=(base_rate or {}).get("text") or "I don't have a cited rate for a case like this",
        basis=(
            humanize_category(getattr(best, "category", "") or "")
            if best is not None
            else "what your documents actually show"
        ),
        next_step="the next step in your gameplan",
    )
