"""X5 — error findings are fully shaped (Brock D-A): a finding asserting a billing ERROR must
carry (i) an ``error_type`` from the enumerated taxonomy, (ii) the specific line items it
implicates, and (iii) the dollar impact. An error claim missing any leg is unactionable and
unverifiable — it must not surface.

CONTRACT SIGNATURE (frozen — template: x1_close_the_loop):
    check_x5(findings) -> X5Verdict
      findings: plain dicts in the runtime Finding shape; error findings are the subset
                whose category asserts an error (vs. informational/context findings)

TODO(brock-content: machine-readable definitions) — implementation (incl. the error_type
enum itself) lands when Brock's X5 definition arrives; until then this raises so nothing
can silently "pass" X5.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class X5Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error_findings_checked: int = 0


def check_x5(findings: list[dict]) -> X5Verdict:
    """Every error finding must carry error_type (enum) + implicated line items + dollar impact."""
    raise NotImplementedError(
        "X5 checker pending Brock's machine-readable definition "
        "(TODO(brock-content: machine-readable definitions))"
    )
