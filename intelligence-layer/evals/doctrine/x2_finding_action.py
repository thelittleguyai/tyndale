"""X2 — surface-only-if-actionable (Brock D-A; contract per 37_x_rules_contracts_DRAFT.md).

THE CONTRACT
    Every finding rendered to the user MUST satisfy ONE of:
      1. it carries ≥1 attached action — a user-executable next step bound to THAT finding
         (a recommendation the gameplan turns into a call step, or a finding-level document
         request); "an action exists somewhere else in the plan" does not pass — the binding
         is finding→action, not page→actions;
      2. OR it is explicitly typed informational context and renders under the context
         treatment (e.g. the §5.4 rung-0 "not an error, here's the real math" reconciliation).

    Canonical failure (the draft's worked example):
        "Your insurer applied your deductible in an unusual order."  (no action, no typing)
        → FAIL: reasons no_attached_action, not_typed_informational.

MECHANICS
    Pure + stdlib-only, loadable by file path (X1's template: same Verdict shape, named-reason
    discipline). All Brock-owned definitions live in doctrine_config (DRAFT pending packet A6)
    — his amendments are a data change there, not an edit here. Inputs are plain dicts in the
    runtime Finding shape (finding_type / category / facts / recommendation / presentation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:  # loaded as a sibling by file path (tests/harness register doctrine_config first)
    import doctrine_config as cfg
except ImportError:  # direct package-style import fallback
    from . import doctrine_config as cfg  # type: ignore[no-redef]


@dataclass
class X2Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    findings_checked: int = 0

    def summary(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        parts = [f"X2 {state} ({self.findings_checked} finding(s))"]
        if self.reasons:
            parts.append("reasons: " + ", ".join(self.reasons))
        if self.notes:
            parts.append("notes: " + ", ".join(self.notes))
        return "; ".join(parts)


def _has_attached_action(finding: dict) -> bool:
    """≥1 action bound to THIS finding, per cfg.X2_ACTION_MEANS."""
    rec = finding.get("recommendation") or {}
    action = rec.get("action") if isinstance(rec, dict) else None
    if isinstance(action, str) and action.strip():
        return True
    facts = finding.get("facts") or {}
    doc_request = facts.get("document_request") if isinstance(facts, dict) else None
    return bool(doc_request)


def _typed_informational(finding: dict) -> bool:
    """Explicit informational typing — the presentation field when upstream writes it, else
    the engine's informational categories (the current typing mechanism; see config note)."""
    presentation = finding.get("presentation")
    if presentation == "informational_context":
        return True
    return (finding.get("category") or "") in cfg.INFORMATIONAL_CATEGORIES


def check_x2(findings: list[dict]) -> X2Verdict:
    """Every finding carries ≥1 action, or is explicitly informational. Named reasons."""
    verdict = X2Verdict(passed=True, findings_checked=len(findings))
    if not findings:
        verdict.notes.append("no_findings (vacuous pass)")
        return verdict
    for f in findings:
        label = str(f.get("category") or f.get("finding_id") or "finding")
        if _has_attached_action(f):
            continue
        if _typed_informational(f):
            verdict.notes.append(f"informational_context: {label}")
            continue
        verdict.passed = False
        verdict.reasons.append(f"no_attached_action+not_typed_informational: {label}")
    return verdict
