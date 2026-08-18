"""Case jurisdiction — which state's rules govern this case (2026-08-19, settings item 2).

Selection ladder, per Phil's ruling: the CASE's own document evidence (the patient-address
state extracted at parse time) WINS over the profile default — a bill from the user's
Wisconsin hospital governs that case even if the profile says they've since moved. The
profile state covers cases whose documents never showed one. Conflicts are LOGGED, never
silently resolved.

Consumption today is deliberately thin: the regime-provenance assumption line names the
jurisdiction and its source, so nothing pretends state rules were applied before the
50-state seed lands (DL-81, check_state_seed — Brock's launch condition). When the seed
activates, laws_regulations retrieval filters on exactly this value; this module is the
one seam.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


def case_jurisdiction(case, profile_state: str | None) -> tuple[str | None, str]:
    """(two-letter state | None, source) — source is 'document' | 'profile' | 'unknown'."""
    doc_state = next(
        (
            str(d["patient_state"])
            for d in ((case.documents if case else None) or [])
            if isinstance(d, dict) and d.get("patient_state")
        ),
        None,
    )
    if doc_state and profile_state and doc_state != profile_state:
        log.info(
            "jurisdiction.document_overrides_profile",
            case_file_id=str(getattr(case, "case_file_id", None)),
            document_state=doc_state,
            profile_state=profile_state,
        )
        return doc_state, "document"
    if doc_state:
        return doc_state, "document"
    if profile_state:
        return profile_state, "profile"
    return None, "unknown"
