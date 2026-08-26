"""Coverage-number checklist items (Brock image-3 item 2, 2026-08-22).

The needs-documents card grows the exact fields that are the highest-leverage missing
inputs in the materiality engine — deductible amount / met, OOP max amount / met — plus a
visit-confirmation item. The list is COMPUTED from the case, never hardcoded:

* a value the documents/SBC already supplied is not asked for (the item is omitted);
* a value the USER entered renders as a completed (checked) item — provenance says which;
* "not sure" is an acknowledged state, kept visible but never nagged as missing.

Values written back are user-attested facts: the save path records provenance
(`user-entered`, timestamp) under ``coverage["user_input_provenance"]`` per the
SourceResult philosophy; a later document that contradicts a user-entered value is the
existing reconcile ladder's job, never a silent overwrite here.
"""

from __future__ import annotations

from app.sources.extraction import plausible_extracted_name

# key → the user-facing label (Brock's exact wordings from the 2026-08-22 feedback).
COVERAGE_NUMBER_ITEMS: tuple[tuple[str, str], ...] = (
    ("deductible_amount", "Deductible amount"),
    ("deductible_met", "Amount spent toward deductible before this visit"),
    ("oop_max_amount", "Out-of-pocket max amount"),
    ("oop_max_met", "Amount spent toward out-of-pocket max before this visit"),
)
VISIT_CONFIRM_KEY = "visit_confirm"
VISIT_CONFIRM_LABEL = "Confirm what your visit was for"
COVERAGE_INPUT_FIELDS: frozenset[str] = frozenset(
    {k for k, _ in COVERAGE_NUMBER_ITEMS} | {VISIT_CONFIRM_KEY}
)
_MAX_CANDIDATES = 4


def _visit_candidates(case) -> list[str]:
    """Tap-to-confirm service descriptions from the bill's own line items — plain-language
    translation first, raw description second. Every candidate passes the extracted-string
    plausibility gate (D4(b) rule: never offer table junk as an option) and the set is
    deduped, order-preserving, capped."""
    seen: set[str] = set()
    out: list[str] = []
    for li in getattr(case, "line_items", None) or []:
        if not isinstance(li, dict):
            continue
        text = (li.get("plain_language_translation") or li.get("raw_description") or "").strip()
        if not text or not plausible_extracted_name(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= _MAX_CANDIDATES:
            break
    return out


def coverage_checklist_items(case) -> list[dict]:
    """The coverage items this case actually needs, with completed/not-sure state."""
    cov = getattr(case, "coverage", None) or {}
    prov = cov.get("user_input_provenance") or {}
    items: list[dict] = []
    for key, label in COVERAGE_NUMBER_ITEMS:
        value = cov.get(key)
        p = prov.get(key) or {}
        user_entered = p.get("source") == "user-entered"
        not_sure = bool(p.get("not_sure"))
        if value is not None and not user_entered:
            continue  # a document (SBC/EOB promotion) supplied it — the audit needn't ask
        items.append(
            {
                "key": key,
                "kind": "number",
                "label": label,
                "value": float(value) if value is not None else None,
                "not_sure": not_sure and value is None,
            }
        )
    confirmed = cov.get("user_visit_description")
    visit_prov = prov.get(VISIT_CONFIRM_KEY) or {}
    if confirmed or not getattr(case, "encounter_confirmations", None):
        items.append(
            {
                "key": VISIT_CONFIRM_KEY,
                "kind": "visit_confirm",
                "label": VISIT_CONFIRM_LABEL,
                "value": confirmed if isinstance(confirmed, str) else None,
                "not_sure": bool(visit_prov.get("not_sure")) and not confirmed,
                "candidates": [] if confirmed else _visit_candidates(case),
            }
        )
    return items
