"""X1 close-the-loop doctrine contract (Brock D-A, July 25) — the CI teeth.

Loads the self-contained checker from intelligence-layer/evals/doctrine (by file path, the
same way the e2e harness does) and proves:
  * Brock's canonical worked failure — the DELIBERATE X1-VIOLATION FIXTURE — is caught with
    named reasons;
  * the real needs_documents thread shape (thread_bridge's checklist payload) passes;
  * X1(c) against the REAL cadence machinery's own functions (nudge_cron._chase_documents /
    _due_stage — the pieces scan_for_nudges composes), not a reimplementation;
  * the X2/X3/X5 stubs exist with frozen signatures and refuse to silently pass.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_DOCTRINE = pathlib.Path(__file__).resolve().parents[2] / "intelligence-layer" / "evals" / "doctrine"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _DOCTRINE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve annotations via sys.modules — register first
    spec.loader.exec_module(mod)
    return mod


x1 = _load("x1_close_the_loop")


def _msg(content: str, *, role: str = "system", kind: str = "system_message", payload: dict | None = None) -> dict:
    return {"role": role, "kind": kind, "content": content, "payload": payload or {"text": content}}


# --- the deliberate X1-violation fixture (Brock's worked example) ------------
def test_brock_canonical_failure_is_caught_with_named_reasons():
    """"To finish this check I need your EOB. Please upload it to continue." — an imperative
    ask with no affordance, no resume promise, a closed case, and no nudge: all three legs
    fail, each with a NAMED reason."""
    thread = [_msg("To finish this check I need your EOB. Please upload it to continue.")]
    verdict = x1.check_x1(thread, case_status="resolved", nudge_state={"eligible": False})
    assert not verdict.passed
    assert verdict.information_requests == 1
    reasons = " | ".join(verdict.reasons)
    assert "no_return_path" in reasons
    assert "case_not_open" in reasons
    assert "no_nudge_scheduled" in reasons


def test_healthy_needs_documents_thread_passes():
    """The real thread_bridge shape: the needs_documents entry carries the checklist payload
    (the structured upload affordance), the case stays audit_incomplete (open), the cadence
    machinery is eligible → X1 holds."""
    checklist = {
        "intro": "To finish your review, Tyndale still needs a couple of documents.",
        "items": [
            {"key": "eob", "label": "Explanation of Benefits (EOB)", "how_to_get": "…", "have": False},
            {"key": "bill", "label": "Itemized bill", "how_to_get": "…", "have": True},
        ],
    }
    thread = [
        _msg("Got your documents — starting the review."),
        _msg(
            "To finish your review, Tyndale still needs a couple of documents.",
            payload={"text": "…", "needs_documents": checklist, "marker": "needs_documents"},
        ),
    ]
    verdict = x1.check_x1(thread, case_status="audit_incomplete", nudge_state={"eligible": True})
    assert verdict.passed, verdict.summary()
    assert verdict.information_requests == 1


def test_resume_language_alone_is_a_return_path():
    """Nudge-style copy — "add it whenever it's handy and Tyndale will finish the review
    automatically" — closes the loop even without a structured affordance payload."""
    thread = [
        _msg("We still need your EOB to lock in the numbers."),
        _msg("You can add it whenever it's handy, and Tyndale will finish the review automatically."),
    ]
    verdict = x1.check_x1(thread, case_status="audit_incomplete", nudge_state={"eligible": True})
    assert verdict.passed, verdict.summary()


def test_verification_request_kind_has_builtin_return_path():
    thread = [_msg("Did this visit include a blood draw?", kind="verification_request", payload={})]
    verdict = x1.check_x1(thread, case_status="encounter_verification_pending", nudge_state={"eligible": True})
    assert verdict.passed, verdict.summary()


def test_user_messages_and_plain_updates_are_never_information_requests():
    thread = [
        _msg("please upload my EOB for me?", role="user", kind="message"),  # user asks US — not X1
        _msg("Your audit is complete — here are the three numbers."),
    ]
    verdict = x1.check_x1(thread, case_status="audit_complete", nudge_state=None)
    assert verdict.passed
    assert verdict.information_requests == 0
    assert any("vacuous" in n for n in verdict.notes)


def test_http_harness_mode_notes_unverified_nudge_never_silent():
    thread = [_msg("We need your itemized bill.", payload={"needs_documents": {"items": [{"key": "bill"}]}})]
    verdict = x1.check_x1(thread, case_status="audit_incomplete", nudge_state=None)
    assert verdict.passed
    assert any("nudge_unverified" in n for n in verdict.notes)


# --- X1(c) against the REAL cadence machinery --------------------------------
def test_nudge_cadence_real_machinery_eligibility():
    """Drive (c) with the cron's own functions (what scan_for_nudges composes per case): a
    coverage-poor case has SBC-chase documents, and the +3d/+14d ladder fires exactly once
    per stage. nudge_state derives from the real pieces — no reimplementation."""
    from app.crons.nudge_cron import _chase_documents, _due_stage

    chase = _chase_documents(None)  # no coverage → deductible/oop/coinsurance all missing
    assert chase, "a coverage-poor case must have load-bearing chase documents"
    assert _due_stage(16, [], 3, 14) == "+14d"
    assert _due_stage(4, [], 3, 14) == "+3d"
    assert _due_stage(4, ["+3d"], 3, 14) is None  # sent → not due again
    assert _due_stage(40, ["+14d"], 3, 14) is None  # ladder exhausted → in-app resurfacing only

    eligible = bool(chase) and _due_stage(4, [], 3, 14) is not None
    thread = [_msg("We still need your SBC.", payload={"needs_documents": {"items": [{"key": "sbc"}]}})]
    verdict = x1.check_x1(thread, case_status="audit_incomplete", nudge_state={"eligible": eligible})
    assert verdict.passed, verdict.summary()

    starved = x1.check_x1(thread, case_status="audit_incomplete", nudge_state={"eligible": False})
    assert not starved.passed
    assert any("no_nudge_scheduled" in r for r in starved.reasons)


# --- X2/X3/X5: frozen signatures, no silent passes ---------------------------
@pytest.mark.parametrize(
    ("module", "func", "verdict_cls"),
    [
        ("x2_finding_action", "check_x2", "X2Verdict"),
        ("x3_missing_input_qualifier", "check_x3", "X3Verdict"),
        ("x5_error_finding_shape", "check_x5", "X5Verdict"),
    ],
)
def test_checkers_exist_with_the_frozen_contract_shape(module: str, func: str, verdict_cls: str):
    """Until 2026-08-17 these were stubs asserted to RAISE, so nothing could silently pass a
    rule we couldn't check. They are now implemented (from 37_x_rules_contracts_DRAFT.md,
    constants in doctrine_config pending Brock's A6 sign-off); this pins the frozen shape —
    Verdict class exported, empty input is an explicit noted vacuous pass, never a raise.
    Their teeth live in test_x2x3x5_contracts.py."""
    # Standalone-safe (the sweep-regression fix exposed the old sibling-test-order
    # dependency): register doctrine_config ourselves when no other file has yet.
    if "doctrine_config" not in sys.modules:
        _load("doctrine_config")
    mod = _load(module)
    assert hasattr(mod, verdict_cls), f"{module} must export {verdict_cls} (frozen contract shape)"
    verdict = getattr(mod, func)([])
    assert verdict.passed and verdict.notes, "empty input must be a NOTED vacuous pass"


# ── the sweep regressions (2026-08-17): affordances X1's detector missed ──────────────────
def test_wrongdoc_next_action_is_a_return_path_and_not_a_bill_is_open():
    """insurance_card_only's fail was the DETECTOR, not the product: the card-branch entry
    carries a typed next_action (rendered as the N2 branch card's action button) and the
    upload route attaches further documents to a not_a_bill case — a redirect, not a
    closure. Both halves pinned."""
    thread = [{
        "kind": "system_message",
        "role": "system",
        "payload": {
            "text": "That looks like an insurance card, not a bill or EOB — add your bill "
                    "and I'll get to work.",
            "wrongdoc_branch": "card",
            "next_action": "add_bill_or_eob",
        },
    }]
    verdict = x1.check_x1(thread, "not_a_bill", nudge_state=None)
    assert verdict.passed, verdict.reasons


def test_unlock_more_checklist_is_a_return_path_on_a_complete_case():
    """Rung-2: the unlock-more card is an ask ("add your SBC…") whose checklist renders with
    the same add-document affordance the needs-documents card has."""
    thread = [{
        "kind": "system_message",
        "role": "system",
        "payload": {
            "text": "Your audit is done — add your plan's SBC and I can pin the math down.",
            "unlock_more": {"intro": "…", "item_hint": "…", "items": [{"key": "sbc", "have": False}]},
        },
    }]
    verdict = x1.check_x1(thread, "audit_complete", nudge_state=None)
    assert verdict.passed, verdict.reasons
