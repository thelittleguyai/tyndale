"""X1 — close-the-loop (Brock decision D-A, July 25): the CI-testable doctrine contract.

THE CONTRACT
    Any assistant/system thread message classified as an ``information_request`` (Tyndale asks
    the user for something) MUST satisfy ALL of:
      (a) return path  — the ask carries a structured upload/response affordance, or the thread
                         contains explicit system-resumes language ("once you add it, Tyndale
                         will finish the review") — the user is never handed a dead-end ask;
      (b) case open    — the case status remains an OPEN state; an information request must
                         never coexist with a closed/terminal-resolved case
                         (no "closed_awaiting_user"-like states);
      (c) nudge        — follow-up is scheduled: the +3d/+14d cadence machinery has (or will
                         pick up) the case's load-bearing item.

    Canonical failure (Brock's worked example): a bare
        "To finish this check I need your EOB. Please upload it to continue."
    with nothing else fails (a) — an imperative ask is not a return path — and, in his
    scenario, (b)/(c) too.

MECHANICS
    Pure + self-contained (stdlib only, no runtime imports) so the e2e harness can load it by
    file path (importlib) and unit tests can drive it with fixtures. This module is the
    TEMPLATE for X2/X3/X5 — same Verdict shape, same named-reason discipline (see the sibling
    stubs). Inputs are plain dicts in the runtime's thread/message shape
    (kind / role / content / payload).

CLASSIFICATION IS AN ENGINEERING SEED
    ``classify_information_request`` is a conservative heuristic (structured needs_documents
    payloads, verification_request kind, ask-language patterns).
    TODO(brock-content: machine-readable definitions) — replace with Brock's classification
    when his X-rule definitions land; the contract shape above does not change.

NUDGE VERIFIABILITY
    The runtime schedules nudges by SCAN (crons/nudge_cron computes eligibility live against
    the DB + the case's nudges_sent ledger) — there are no pre-created cadence rows. So (c)
    is verifiable only where DB state is reachable:
      * unit tests / in-process harnesses pass ``nudge_state`` built from the REAL
        scan_for_nudges machinery → (c) has full teeth;
      * the HTTP-only e2e harness passes ``nudge_state=None`` → (c) is recorded as
        ``nudge_unverified`` (a note, not a failure) rather than silently asserted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Case statuses considered OPEN (an information request may — must — leave the case here).
# Everything else (resolved, archived, and future attest_declined-style closes) is a
# closed/terminal-resolved state in which an unanswered ask would strand the user.
OPEN_STATUSES = frozenset(
    {
        "uploaded",
        "extraction_complete",
        "extraction_failed",  # open: the re-upload path stays live
        "encounter_verification_pending",
        "encounter_verified",
        "awaiting_eob_confirmation",
        "audit_running",
        "audit_incomplete",  # incl. reason=needs_documents — the X1 archetype
        "audit_complete",  # open for outcome follow-up / added documents
        # A REDIRECT, not a closure (§A2 state 2, corrected 2026-08-18 from the dev sweep's
        # insurance_card_only fail): the upload route attaches further documents to a
        # not_a_bill case and the typed wrongdoc next_action routes exactly there — the ask
        # ("add your bill") is answerable in place. The return-path check (a) still applies.
        "not_a_bill",
    }
)

# An ask: request verbs aimed at a document/input, or an explicit "to finish/continue" gate.
_ASK_RE = re.compile(
    r"(?i)\b(upload|send|attach|provide|share|add)\b.{0,60}?"
    r"\b(eob|bill|statement|document|card|sbc|summary|photo|copy|it)\b"
    r"|\bneed (?:your|the|a|an)\b"
    r"|\bto (?:finish|continue|complete)\b"
)

# System-resumes language — a promise the loop closes, not an imperative to the user.
# (The "still here / keep working / not going anywhere" family was added after the §12
# program-handoff copy tripped this check: a warm handoff that promises Tyndale keeps working
# the billing side IS a return path, and the original pattern list didn't cover it.)
_RESUME_RE = re.compile(
    r"(?i)\b(?:i|we|tyndale)(?:'ll| will)\s+(?:pick|resume|finish|continue|re-?run|complete|keep)"
    r"|\bautomatically (?:finish|resume|re-?run|complete)"
    r"|\bonce (?:you|we have|it'?s)\b"
    r"|\bwhen(?:ever)? (?:you (?:upload|add|send)|it'?s handy)\b"
    r"|\b(?:i'?m|we'?re) still here\b"
    r"|\b(?:i'?m|we'?re) not going anywhere\b"
    r"|\bkeep (?:working|going|watching)\b"
)


@dataclass
class X1Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)  # named failures, empty when passed
    notes: list[str] = field(default_factory=list)  # non-failing observations
    information_requests: int = 0

    def summary(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        parts = [f"X1 {state} ({self.information_requests} information_request(s))"]
        if self.reasons:
            parts.append("reasons: " + ", ".join(self.reasons))
        if self.notes:
            parts.append("notes: " + ", ".join(self.notes))
        return "; ".join(parts)


def _text_of(message: dict) -> str:
    payload = message.get("payload") or {}
    return str(message.get("content") or payload.get("text") or "")


def classify_information_request(message: dict) -> bool:
    """True when a system/assistant thread entry asks the user for an input.

    Conservative engineering seed — see module docstring.
    TODO(brock-content: machine-readable definitions)."""
    if (message.get("role") or "system") == "user":
        return False
    payload = message.get("payload") or {}
    if payload.get("needs_documents"):
        return True
    if message.get("kind") == "verification_request":
        return True
    return bool(_ASK_RE.search(_text_of(message)))


def _has_return_path(message: dict, thread: list[dict]) -> bool:
    """(a): a structured affordance on the ask itself, or resume language in the thread."""
    payload = message.get("payload") or {}
    needs = payload.get("needs_documents") or {}
    if isinstance(needs, dict) and needs.get("items"):
        return True  # the checklist IS the upload affordance (rendered with add-document)
    unlock = payload.get("unlock_more") or {}
    if isinstance(unlock, dict) and unlock.get("items"):
        return True  # rung-2: the unlock checklist renders with the same add-document path
    if payload.get("next_action"):
        # The typed wrongdoc affordance (§A2 state 2) — rendered as an inline action button
        # (the N2 branch card), routing to the case's own upload. Structured, not prose.
        return True
    if message.get("kind") == "verification_request":
        return True  # rendered with its own confirm/deny response affordance
    # An explicit structured "the case remains open" marker (e.g. the §12 program handoff):
    # the loop is declared open in DATA, not just asserted in prose.
    for value in payload.values():
        if isinstance(value, dict) and value.get("case_stays_open"):
            return True
    for m in thread:
        if (m.get("role") or "system") != "user" and _RESUME_RE.search(_text_of(m)):
            return True
    return False


def check_x1(
    thread: list[dict],
    case_status: str,
    nudge_state: dict | None = None,
) -> X1Verdict:
    """Evaluate the X1 contract over a case's thread + post-scenario state.

    ``nudge_state`` (DB-derived, e.g. from scan_for_nudges + the nudges_sent ledger):
        {"eligible": bool, ...}   — eligible=True means the cadence machinery has/will
                                    pick up the case's load-bearing item.
        None                      — nudge state unreachable (HTTP-only harness): (c) is
                                    noted unverified, never silently passed as asserted.
    """
    verdict = X1Verdict(passed=True)
    asks = [m for m in thread if classify_information_request(m)]
    verdict.information_requests = len(asks)
    if not asks:
        verdict.notes.append("no_information_request (vacuous pass)")
        return verdict

    for ask in asks:
        if not _has_return_path(ask, thread):
            verdict.passed = False
            snippet = _text_of(ask)[:60]
            verdict.reasons.append(f"no_return_path: {snippet!r}")

    if case_status not in OPEN_STATUSES:
        verdict.passed = False
        verdict.reasons.append(f"case_not_open: status={case_status!r}")

    if nudge_state is None:
        verdict.notes.append("nudge_unverified (no DB access — assert (c) in-process)")
    elif not nudge_state.get("eligible"):
        verdict.passed = False
        verdict.reasons.append("no_nudge_scheduled: cadence machinery will not pick this case up")

    return verdict
