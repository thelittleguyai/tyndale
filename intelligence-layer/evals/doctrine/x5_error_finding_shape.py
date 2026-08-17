"""X5 — name-the-specific-error (contract per 37_x_rules_contracts_DRAFT.md).

THE CONTRACT
    Every finding classed as an ERROR (distinct from opportunities and informational context)
    MUST carry all three:
      1. `error_type` from the enum in doctrine_config — never null, never free text; the
         escape hatch `other_billing_error` is permitted ONLY with a named sub-label;
      2. ≥1 implicated LINE-ITEM ref (a document-level error like balance billing may
         reference the bill-total line, but the ref must exist);
      3. a dollar impact — a computed amount, a range, or the explicit typed
         `impact_unknown_reason` from the config's reasons; silent absence fails.

    Canonical failure (the draft's worked example):
        "Something looks wrong with the charges on this bill — worth asking your provider."
        → FAIL: reasons error_type_missing, no_line_item_ref, impact_missing_untyped.

ERROR-NESS (engineering seed, DRAFT like everything in doctrine_config)
    Upstream doesn't write `finding_class` yet. A finding counts as an error when it is not
    informational (per config) AND it either carries/derives an error_type or claims a dollar
    gap. The runtime annotates `error_type` at the read seam (app/sources/error_types.py)
    from the SAME config, so by the time findings reach this checker the unambiguous cases
    are typed and the rest carry the escape hatch with the category as sub-label.

MECHANICS
    Pure + stdlib-only, X1's template. Finding shape: runtime dicts
    (category / finding_type / facts / error_type / error_type_sub_label / presentation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    import doctrine_config as cfg
except ImportError:
    from . import doctrine_config as cfg  # type: ignore[no-redef]


@dataclass
class X5Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors_checked: int = 0

    def summary(self) -> str:
        state = "PASS" if self.passed else "FAIL"
        parts = [f"X5 {state} ({self.errors_checked} error finding(s))"]
        if self.reasons:
            parts.append("reasons: " + ", ".join(self.reasons))
        if self.notes:
            parts.append("notes: " + ", ".join(self.notes))
        return "; ".join(parts)


def derive_error_type(finding: dict) -> tuple[str | None, str | None]:
    """(error_type, sub_label) from the config's unambiguous maps, else the escape hatch.

    Shared derivation logic: the runtime's read-seam annotator mirrors exactly this call, so
    the checker and the product can never disagree about what a category means. Returns
    (None, None) for informational findings — they have no error type at all.
    """
    explicit = finding.get("error_type")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip(), finding.get("error_type_sub_label")
    category = str(finding.get("category") or "")
    if category in cfg.INFORMATIONAL_CATEGORIES or finding.get("presentation") == "informational_context":
        return None, None
    mapped = cfg.CATEGORY_TO_ERROR_TYPE.get(category)
    if mapped:
        return mapped, None
    mapped = cfg.FINDING_TYPE_TO_ERROR_TYPE.get(str(finding.get("finding_type") or ""))
    if mapped:
        return mapped, None
    return cfg.X5_ESCAPE_HATCH, category or "uncategorized"


def _is_error(finding: dict) -> bool:
    et, _ = derive_error_type(finding)
    if et is None:
        return False
    facts = finding.get("facts") or {}
    gap = facts.get("gap") if isinstance(facts, dict) else None
    has_gap = isinstance(gap, (int, float)) and not isinstance(gap, bool) and gap > 0
    # A typed (non-escape) error is an error regardless of gap; escape-hatch findings only
    # count as errors when they claim money — otherwise they're unclassified noise the audit
    # shouldn't have surfaced (which X2 catches on its own axis).
    return et != cfg.X5_ESCAPE_HATCH or has_gap


def _line_item_refs(finding: dict) -> list[str]:
    facts = finding.get("facts") or {}
    if not isinstance(facts, dict):
        return []
    refs = facts.get("line_item_refs")
    if isinstance(refs, list) and refs:
        return [str(r) for r in refs]
    single = facts.get("line_item_id")
    return [str(single)] if single else []


def _has_impact(finding: dict) -> tuple[bool, str | None]:
    facts = finding.get("facts") or {}
    if not isinstance(facts, dict):
        return False, None
    gap = facts.get("gap")
    if isinstance(gap, (int, float)) and not isinstance(gap, bool):
        return True, None
    low, high = facts.get("impact_low"), facts.get("impact_high")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return True, None
    reason = facts.get("impact_unknown_reason")
    if reason in cfg.X5_IMPACT_UNKNOWN_REASONS:
        return True, str(reason)
    return False, None


def check_x5(findings: list[dict]) -> X5Verdict:
    """Every error finding: enum error_type (+sub-label on the escape hatch) · ≥1 line-item
    ref · impact or a typed unknown-reason. Named reasons per leg."""
    errors = [f for f in findings if _is_error(f)]
    verdict = X5Verdict(passed=True, errors_checked=len(errors))
    if not errors:
        verdict.notes.append("no_error_findings (vacuous pass)")
        return verdict

    for f in errors:
        label = str(f.get("category") or f.get("finding_id") or "finding")
        et, sub = derive_error_type(f)
        if et is None or et not in cfg.X5_ERROR_TYPES:
            verdict.passed = False
            verdict.reasons.append(f"error_type_missing_or_unenum: {label} ({et!r})")
        elif et == cfg.X5_ESCAPE_HATCH:
            if not (isinstance(sub, str) and sub.strip()):
                verdict.passed = False
                verdict.reasons.append(f"escape_hatch_without_sub_label: {label}")
            else:
                verdict.notes.append(f"escape_hatch({sub}): {label}")

        if not _line_item_refs(f):
            verdict.passed = False
            verdict.reasons.append(f"no_line_item_ref: {label}")

        ok, reason = _has_impact(f)
        if not ok:
            verdict.passed = False
            verdict.reasons.append(f"impact_missing_untyped: {label}")
        elif reason:
            verdict.notes.append(f"impact_unknown({reason}): {label}")
    return verdict
