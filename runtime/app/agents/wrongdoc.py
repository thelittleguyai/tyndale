"""Wrong-document redirect (Brock July 16 §A2 state 2 / script §5ii).

The generic "this isn't a medical bill" dead-end becomes a TYPED redirect: the classifier
already knows what the upload IS, so each kind gets its own honest next step.

    insurance card alone  → offer the card-upload flow (it's useful — just not auditable alone)
    plan summary / SBC    → attach it to coverage, thank them, explain what it unlocks
    GFE                   → same coverage-ish branch (a real document, not an auditable bill)
    clinical record       → honest "I can't audit this, here's what I can use"
    unknown / unreadable  → the existing generic redirect

Every branch carries a ``next_action`` — the affordance the thread renders — so a wrong-doc
upload never terminates without a return path (X1 close-the-loop).
"""

from __future__ import annotations

from typing import NamedTuple

# Document types that are REAL medical/insurance documents but carry no auditable charges.
# A case whose only readable documents are these is a wrong-doc redirect, not a failure.
CARD_TYPES = frozenset({"insurance_card"})
COVERAGE_TYPES = frozenset({"sbc", "gfe"})
CLINICAL_TYPES = frozenset({"clinical_record", "clinical_note", "medical_record"})
# Anything here CAN produce line items, so its absence of them is a real extraction problem.
AUDITABLE_TYPES = frozenset(
    {
        "eob", "ma_eob", "msn", "tricare_eob", "bill", "itemized_bill", "collections_notice",
        "denial_letter", "mco_notice", "va_statement", "community_care_auth",
    }
)


class WrongDoc(NamedTuple):
    branch: str  # card | sbc | clinical | unknown
    key: str  # the orchestration-script registry key
    next_action: str  # the affordance the thread offers (the X1 return path)


_BRANCHES = {
    "card": WrongDoc("card", "wrongdoc.card", "upload_card_flow"),
    "sbc": WrongDoc("sbc", "wrongdoc.sbc", "attach_to_coverage"),
    "clinical": WrongDoc("clinical", "wrongdoc.clinical", "add_bill_or_eob"),
    "unknown": WrongDoc("unknown", "wrongdoc.unknown", "add_bill_or_eob"),
}


def _types(documents) -> set[str]:
    out: set[str] = set()
    for d in documents or []:
        t = getattr(d, "document_type", None) if not isinstance(d, dict) else d.get("document_type")
        out.add(t or "unclassified")
    return out


def classify_wrong_document(documents) -> WrongDoc | None:
    """The redirect branch for a case whose readable documents yielded nothing auditable, or
    None when at least one document COULD have produced line items (that's a real extraction
    problem, not a wrong document — never mislabel it).

    ``documents`` may be dicts or DocumentExtraction objects; only readable ones should be
    passed in (the caller already filters)."""
    types = _types(documents)
    if not types:
        return None
    if types & AUDITABLE_TYPES:
        return None  # an auditable doc is present → not a wrong-document case
    if types & CARD_TYPES:
        return _BRANCHES["card"]
    if types & COVERAGE_TYPES:
        return _BRANCHES["sbc"]
    if types & CLINICAL_TYPES:
        return _BRANCHES["clinical"]
    return _BRANCHES["unknown"]
