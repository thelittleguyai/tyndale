"""error_type annotation at the finding read seam (X5 wiring, 2026-08-17).

The X5 contract wants every ERROR finding to carry a typed `error_type`. Upstream (the
agents, the encounter path) doesn't set one yet, so the runtime derives it at READ time —
the same seam that stamps the grounding line — from the ONE config module the checkers use:
`intelligence-layer/evals/doctrine/doctrine_config.py` (DRAFT pending Brock, packet A6).

Deriving at read time rather than persist time is deliberate:
  * one chokepoint instead of four Finding-creation sites;
  * it applies retroactively to every finding already in the DB, no backfill;
  * when Brock amends the taxonomy, existing findings re-derive under his mapping instead of
    being frozen under the draft's.

The derivation itself lives in the checker module (`x5_error_finding_shape.derive_error_type`)
and is LOADED from there by file path — the product and the contract can never disagree about
what a category means, because they run the same function. Provenance is explicit: annotated
findings carry error_type_source="derived_draft" so nobody mistakes a derived type for an
upstream-asserted one.
"""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from typing import Any

import structlog

from app.agents.context_loader import _intelligence_layer_root

log = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _doctrine():
    """Load doctrine_config + the x5 checker from intelligence-layer by file path.

    Returns the x5 module (whose derive_error_type is the shared derivation), or None when
    the doctrine directory is unreadable — findings then go unannotated, WARNED once, and the
    X5 harness check reports the absence rather than anything guessing.
    """
    root = _intelligence_layer_root() / "evals" / "doctrine"
    try:
        for name in ("doctrine_config", "x5_error_finding_shape"):
            if name in sys.modules:
                continue
            spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod  # register BEFORE exec so the sibling import resolves
            spec.loader.exec_module(mod)
        return sys.modules["x5_error_finding_shape"]
    except Exception as exc:  # noqa: BLE001 — annotation is best-effort, never a 500
        log.warning("error_types.doctrine_unloadable", error=str(exc), root=str(root))
        return None


def annotate_error_type(finding: Any) -> Any:
    """Stamp error_type / error_type_sub_label / error_type_source onto a FindingOut-like
    object. Explicit upstream values are respected untouched; informational findings get no
    type at all (X5 does not apply to them)."""
    x5 = _doctrine()
    if x5 is None:
        return finding
    as_dict = {
        "error_type": getattr(finding, "error_type", None),
        "error_type_sub_label": getattr(finding, "error_type_sub_label", None),
        "category": getattr(finding, "category", None),
        "finding_type": getattr(finding, "finding_type", None),
        "facts": getattr(finding, "facts", None),
        "presentation": getattr(finding, "presentation", None),
    }
    had_explicit = bool(as_dict["error_type"])
    try:
        error_type, sub_label = x5.derive_error_type(as_dict)
        finding.error_type = error_type
        finding.error_type_sub_label = sub_label
        if error_type is not None:
            finding.error_type_source = "upstream" if had_explicit else "derived_draft"
    except Exception as exc:  # noqa: BLE001 — a finding the draft can't type must still render
        log.warning("error_types.derivation_failed", error=str(exc))
    return finding
