"""X2 — finding ⇒ action (Brock D-A): every surfaced finding carries at least one user
action, or is explicitly typed ``informational_context``. A finding with no action and no
informational marker strands the user with a problem and no path — the finding-level
sibling of X1's close-the-loop rule.

CONTRACT SIGNATURE (frozen — the template established by x1_close_the_loop):
    check_x2(findings) -> X2Verdict
      findings: plain dicts in the runtime Finding shape
                (finding_type / category / facts / recommendation / status ...)

TODO(brock-content: machine-readable definitions) — implementation lands when Brock's
X2 definition arrives; until then this raises so nothing can silently "pass" X2.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class X2Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    findings_checked: int = 0


def check_x2(findings: list[dict]) -> X2Verdict:
    """Every finding must carry ≥1 action (recommendation) or be typed informational_context."""
    raise NotImplementedError(
        "X2 checker pending Brock's machine-readable definition "
        "(TODO(brock-content: machine-readable definitions))"
    )
