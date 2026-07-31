"""X3 — incomplete-input figures are qualified (Brock D-A): any dollar figure computed from
incomplete inputs must carry a qualifier NAMING the missing input ("assuming your deductible
is met — upload your SBC to confirm"), never an unqualified number the user will read as
final. The graceful-degradation doctrine, made checkable.

CONTRACT SIGNATURE (frozen — template: x1_close_the_loop):
    check_x3(figures) -> X3Verdict
      figures: plain dicts, each a rendered figure with its provenance
               ({"value": ..., "inputs_missing": [...], "qualifier_text": ...})

TODO(brock-content: machine-readable definitions) — implementation lands when Brock's
X3 definition arrives; until then this raises so nothing can silently "pass" X3.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class X3Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    figures_checked: int = 0


def check_x3(figures: list[dict]) -> X3Verdict:
    """Every incomplete-input figure must carry a qualifier naming the missing input."""
    raise NotImplementedError(
        "X3 checker pending Brock's machine-readable definition "
        "(TODO(brock-content: machine-readable definitions))"
    )
