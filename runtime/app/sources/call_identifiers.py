"""The case's call identifiers — what the user reads aloud and what they dial (delta B4).

One module owns three jobs so they can't drift apart:

1. **Promotion** — which per-document value becomes the case's primary (`derive_call_identifiers`).
2. **Party routing** — which identifier and which phone belong to a given call (`for_party`).
3. **The registry variable resolver** — the typed fields as `{claim_number}` / `{account_number}`
   slots for the orchestration script (`script_variables`).

Two rules run through all three:

* **Typed, never inferred (DL-39).** Every value here was extracted at parse time into a typed
  field. Nothing is regexed out of finding prose at render time, and no phone number is ever
  looked up externally — if a document didn't print one, the user doesn't get a dial button.
* **Absent means absent.** A missing identifier is omitted, not blanked. `script_variables`
  returns only the keys it actually has, so an authored string using `{claim_number}` on a case
  without one renders the §5 degradation variant (his §0 rule 2) instead of "claim number ."
"""

from __future__ import annotations

from typing import Any, NamedTuple

from app.sources.document_classifier import PAYER_ISSUED_TYPES, PROVIDER_ISSUED_TYPES


class CallIdentifiers(NamedTuple):
    """The four typed fields, as the case carries them. Any of them may be None."""

    claim_number: str | None = None
    account_number: str | None = None
    provider_phone: str | None = None
    payer_phone: str | None = None


class PartyReference(NamedTuple):
    """What one call needs: the identifier to quote, and the number to dial.

    `reference_kind` is a typed discriminator ('claim' | 'account'), not a label — the client
    owns the words, the same way it owns "When they pick up".
    """

    reference_kind: str | None = None
    reference_number: str | None = None
    phone: str | None = None


def _clean(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _first_from(documents: list[dict], field: str, types: frozenset[str]) -> str | None:
    """First non-empty `field` among documents of an owning `types` — first hit wins.

    Type-scoped on purpose: a claim number is promoted from a payer-issued document and an
    account number from a provider-issued one, so a case holding both an EOB and a bill gets
    each field from the document that actually assigns it rather than from whichever uploaded
    first. A document of neither type contributes nothing.
    """
    for d in documents:
        if d.get("document_type") in types:
            if (value := _clean(d.get(field))) is not None:
                return value
    return None


def derive_call_identifiers(documents: list[Any] | None) -> CallIdentifiers:
    """The case's primary identifiers, promoted from its per-document typed fields.

    The document entries remain the full truth for a multi-document case (three EOBs carry
    three claim numbers); this is the one set the call scripts default to.
    """
    docs = [d for d in (documents or []) if isinstance(d, dict)]
    return CallIdentifiers(
        claim_number=_first_from(docs, "claim_number", PAYER_ISSUED_TYPES),
        account_number=_first_from(docs, "account_number", PROVIDER_ISSUED_TYPES),
        # A phone is attributed by who ISSUED the document it was printed on — the number on a
        # bill reaches the billing office, the number on an EOB reaches the plan.
        provider_phone=_first_from(docs, "contact_phone", PROVIDER_ISSUED_TYPES),
        payer_phone=_first_from(docs, "contact_phone", PAYER_ISSUED_TYPES),
    )


def of_case(case: Any) -> CallIdentifiers:
    """The typed columns off a case row (the promoted primaries)."""
    return CallIdentifiers(
        claim_number=_clean(getattr(case, "claim_number", None)),
        account_number=_clean(getattr(case, "account_number", None)),
        provider_phone=_clean(getattr(case, "provider_phone", None)),
        payer_phone=_clean(getattr(case, "payer_phone", None)),
    )


def for_party(ids: CallIdentifiers, party: str) -> PartyReference:
    """What to quote and what to dial for a call to `party` ('payer' | 'provider').

    A payer call is about a CLAIM; a provider call is about an ACCOUNT. Quoting the wrong one
    wastes the call, so the identifier is chosen by who is being called, never by availability
    — a case with only an account number gives a payer call no reference at all, which is the
    honest state.
    """
    if party == "payer":
        return PartyReference("claim", ids.claim_number, ids.payer_phone)
    return PartyReference("account", ids.account_number, ids.provider_phone)


def script_variables(ids: CallIdentifiers) -> dict[str, str]:
    """The identifiers as orchestration-script slots — PRESENT VALUES ONLY.

    Omission is load-bearing: `orchestration_step` degrades a string whose slot has no value
    (his §0 rule 2), so leaving the key out is what makes a missing claim number render the
    §5 variant instead of a blank or a raw `{claim_number}`.
    """
    return {k: v for k, v in ids._asdict().items() if v}
