"""The analytics event registry + PHI-free validator (Rule 2).

This module is the ONLY place event names and their property schemas are declared. A property
is one of exactly three types — an ENUM (a fixed set of allowed string tokens), a NUMBER, or a
BOOLEAN. There is deliberately no free-text/string type: "a property schema containing a string
type must be an enum" is therefore enforced by construction — an un-enumerated string is
unrepresentable. This is what makes the event stream PHI-free by design.

``validate_event`` rejects (a) unregistered event names, (b) unregistered properties, and
(c) values that don't conform to the property's type (a string not in the enum's set, a bool
where a number is expected, etc.). Callers turn a rejection into a dropped write + a counter —
never a raised error on the product path (see ``app.analytics.emit``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PropType(str, Enum):
    ENUM = "enum"  # a fixed set of allowed string tokens — the ONLY way a string enters an event
    NUMBER = "number"  # int or float (a bool is NOT accepted as a number)
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class PropSpec:
    type: PropType
    values: tuple[str, ...] = ()  # non-empty ONLY for ENUM; the closed allow-list

    def __post_init__(self) -> None:
        if self.type is PropType.ENUM and not self.values:
            raise ValueError("an ENUM property must declare a non-empty value set (PHI-free rule)")
        if self.type is not PropType.ENUM and self.values:
            raise ValueError("only an ENUM property may declare values")


def enum_prop(*values: str) -> PropSpec:
    return PropSpec(PropType.ENUM, tuple(values))


def num_prop() -> PropSpec:
    return PropSpec(PropType.NUMBER)


def bool_prop() -> PropSpec:
    return PropSpec(PropType.BOOLEAN)


@dataclass(frozen=True)
class EventSpec:
    props: dict[str, PropSpec] = field(default_factory=dict)
    # Funnel truth is server-known — a server_only event that arrives via POST /v1/events is
    # dropped (the client is never trusted to assert it happened).
    server_only: bool = True
    # Billing-dependent events: registered now (names + schemas frozen), emitted nowhere until the
    # billing rework lands. The funnel panel renders them "not yet live".
    not_yet_live: bool = False


# --- shared enum value sets -------------------------------------------------
_DOC_TYPES = (
    "eob", "itemized_bill", "bill", "insurance_card", "sbc", "denial_letter",
    "collections_notice", "mco_notice", "unclassified", "other",
)
_STAGES = ("extraction", "translate", "encounter", "audit")
_VERIFY_ANSWERS = ("yes", "no", "not_sure")
_NUDGE_STAGES = ("first", "second")
_OUTCOME_RESOLVED = ("yes", "partial", "no")
# The three "How did it go?" routes in call mode. None of them is a resolution — see
# call_outcome_recorded below.
_CALL_OUTCOME_ROUTES = ("fixing_it", "pushed_back", "left_message")
_REFUSAL_CATEGORIES = ("crisis", "medical_advice", "legal_advice", "financial_advice", "out_of_scope", "other")
# §A2 state 1 attest relationships — mirrors app.agents.attest.RELATIONSHIPS (enum, never a
# name). Brock's §3.1 seven-option menu.
_RELATIONSHIPS = (
    "spouse_partner", "parent_guardian", "adult_child_caregiver", "healthcare_poa",
    "court_guardian", "executor", "other",
)
# UTM capture is sanitized to closed allow-lists (Rule 2): a raw campaign string would be free
# text, so only source + medium are captured, each coerced to the nearest known token or "other".
_ATTRIB_SOURCES = ("google", "bing", "facebook", "instagram", "tiktok", "reddit", "youtube",
                   "email", "referral", "direct", "organic", "other")
_ATTRIB_MEDIUMS = ("cpc", "organic", "social", "email", "referral", "affiliate", "display", "other")


# --- the registry -----------------------------------------------------------
# name -> EventSpec. Grouped by dashboard panel. server_only defaults True; the few client-only
# (presentation) events set it False so they may arrive via POST /v1/events.
REGISTRY: dict[str, EventSpec] = {
    # §1 Funnel (server-known) ------------------------------------------------
    "upload_started": EventSpec({"file_count": num_prop()}),
    "documents_accepted": EventSpec({"doc_count": num_prop()}),
    "extraction_succeeded": EventSpec({"doc_type": enum_prop(*_DOC_TYPES)}),
    "extraction_failed": EventSpec(
        {"doc_type": enum_prop(*_DOC_TYPES), "reason": enum_prop("unreadable", "wrong_type", "empty", "other")}
    ),
    "verification_answered": EventSpec(
        {"answer": enum_prop(*_VERIFY_ANSWERS), "question_position": num_prop()}
    ),
    "mapper_suggested": EventSpec(),
    "mapper_confirmed": EventSpec(),
    "mapper_fallback": EventSpec({"kind": enum_prop("full", "partial")}),
    "audit_started": EventSpec(),
    "stage_completed": EventSpec({"stage": enum_prop(*_STAGES), "duration_ms": num_prop()}),
    "audit_completed": EventSpec(),  # disclosure-tier mix is derived at aggregation, not carried here
    "audit_needs_documents": EventSpec(),
    "audit_system_error": EventSpec(),
    "reveal_viewed": EventSpec(),
    # §2 Engagement -----------------------------------------------------------
    # Close-the-loop (flagship): case-level + idempotent per case, so the rate is
    # distinct-cases-satisfied ÷ distinct-cases-issued (per-doc-type grain is a P1 enhancement).
    "document_request_issued": EventSpec(),
    "document_request_satisfied": EventSpec(),
    # `kind` splits the two nudges the 2026-08-17 cron split created: chase (missing document)
    # vs checkin (Brock §11.5 follow-through). Same cadence, different message and premise.
    "nudge_sent": EventSpec({"stage": enum_prop(*_NUDGE_STAGES), "kind": enum_prop("chase", "checkin")}),
    "nudge_responded": EventSpec({"stage": enum_prop(*_NUDGE_STAGES), "kind": enum_prop("chase", "checkin")}),
    "reaudit_delta": EventSpec({"material": bool_prop()}),  # $25/5% materiality (reused constants)
    # call mode is client-side presentation → not server-known
    "call_step_viewed": EventSpec({"step_index": num_prop()}, server_only=False),
    # What happened on a call the user actually made — Brock's outcome-capture DENOMINATOR.
    # Deliberately separate from outcome_reported: none of these three routes resolves a case
    # ("they said they'd fix it" is a claim by the party we're auditing, not a recovery), so
    # this event carries no money and never feeds recovered_so_far.
    "call_outcome_recorded": EventSpec({"route": enum_prop(*_CALL_OUTCOME_ROUTES)}),
    # §3 Outcomes -------------------------------------------------------------
    "outcome_reported": EventSpec(
        {"resolved": enum_prop(*_OUTCOME_RESOLVED), "amount_saved": num_prop()}
    ),
    # §4 Accuracy & trust -----------------------------------------------------
    "finding_feedback": EventSpec({"thumbs": enum_prop("up", "down")}),
    # §6 Compliance counters (COUNT-ONLY, no content) -------------------------
    "crisis_fire_count": EventSpec(),
    # Attest-and-proceed (§A2 state 1). The relationship ENUM only — the patient name lives in
    # the encrypted audit envelope, never here (Rule 2: PHI-free by construction).
    "attestation_required": EventSpec(),
    "attestation_recorded": EventSpec({"relationship": enum_prop(*_RELATIONSHIPS)}),
    "attestation_declined": EventSpec(),
    # Wrong-document redirect (§A2 state 2) — which branch the upload was routed to.
    "wrong_document_redirect": EventSpec({"branch": enum_prop("card", "sbc", "clinical", "unknown")}),
    # §A2 state 4 declines — which decline fired (count-only, never the utterance).
    "decline_state_shown": EventSpec({"kind": enum_prop("fabrication", "guarantee")}),
    # §A2 state 5 — external-program handoff + the access/deletion request intake stub.
    "program_handoff_shown": EventSpec({"program": enum_prop("pace", "other")}),
    # Registered now (name + schema frozen), emitted nowhere yet: the intake is deliberately
    # UNAUTHENTICATED and analytics_events.user_id is NOT NULL, so an anonymous row has nowhere
    # to land. The encrypted access_request audit event is the record until analytics grows an
    # anonymous path — at which point this flips live with no schema churn.
    "access_request_received": EventSpec(
        {"request_type": enum_prop("access", "deletion", "correction")}, not_yet_live=True
    ),
    "refusal_event": EventSpec({"category": enum_prop(*_REFUSAL_CATEGORIES)}),
    "consent_opt_in": EventSpec(),
    "consent_withdrawn": EventSpec(),
    "deletion_requested": EventSpec(),
    "deletion_completed": EventSpec({"hours_to_complete": num_prop()}),
    # Acquisition (sanitized enums only) --------------------------------------
    "signup_attribution": EventSpec(
        {"source": enum_prop(*_ATTRIB_SOURCES), "medium": enum_prop(*_ATTRIB_MEDIUMS)}
    ),
    # Billing-dependent — registered now, emitted nowhere until billing lands -
    "unlock_viewed": EventSpec(not_yet_live=True),
    "unlock_purchased": EventSpec(not_yet_live=True),
    "tier_converted": EventSpec(
        {"from_tier": enum_prop("free", "first_case", "complete"),
         "to_tier": enum_prop("free", "first_case", "complete")},
        not_yet_live=True,
    ),
}

# Names reserved for P1/P2 (event names claimed, no schema/emission yet — so a future phase can't
# collide). Not validatable targets; listed so the registry is the one source of truth.
RESERVED_FUTURE_NAMES: frozenset[str] = frozenset({
    "support_ticket_opened", "sms_sent", "sms_responded", "web_vital_reported",
})


class EventValidationError(ValueError):
    """Raised by validate_event on an unregistered name or non-conforming property."""


def _coerce_number(v: object) -> float:
    # bool is a subclass of int — reject it explicitly so a boolean can't masquerade as a number.
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EventValidationError(f"expected a number, got {type(v).__name__}")
    return float(v)


def validate_event(name: str, properties: dict | None) -> dict:
    """Validate a candidate event against the registry and return the normalized properties.

    Raises EventValidationError on: an unregistered name, an unregistered property, a value whose
    type doesn't match the spec, or a missing required property. No free-text ever survives: the
    only string-valued type is ENUM, checked against its closed set."""
    spec = REGISTRY.get(name)
    if spec is None:
        raise EventValidationError(f"unregistered event name: {name!r}")
    props = properties or {}
    if not isinstance(props, dict):
        raise EventValidationError("properties must be an object")

    unknown = set(props) - set(spec.props)
    if unknown:
        raise EventValidationError(f"unregistered properties for {name!r}: {sorted(unknown)}")

    out: dict[str, object] = {}
    for key, pspec in spec.props.items():
        if key not in props:
            raise EventValidationError(f"missing property {key!r} for {name!r}")
        val = props[key]
        if pspec.type is PropType.ENUM:
            if not isinstance(val, str) or val not in pspec.values:
                raise EventValidationError(
                    f"{name}.{key}: {val!r} is not one of {pspec.values} (no free text allowed)"
                )
            out[key] = val
        elif pspec.type is PropType.NUMBER:
            out[key] = _coerce_number(val)
        else:  # BOOLEAN
            if not isinstance(val, bool):
                raise EventValidationError(f"{name}.{key}: expected a boolean, got {type(val).__name__}")
            out[key] = val
    return out


def coerce_enum(name: str, key: str, value: str, default: str = "other") -> str:
    """Server-side emit convenience: map an open value onto the property's enum, falling back to
    `default` (which must itself be a member) rather than dropping the event. Used where the raw
    value (a doc_type, a UTM source) comes from upstream data that may not be in the allow-list."""
    spec = REGISTRY.get(name)
    if spec is None:
        return default
    pspec = spec.props.get(key)
    if pspec is None or pspec.type is not PropType.ENUM:
        return value
    if value in pspec.values:
        return value
    return default if default in pspec.values else pspec.values[-1]


def _self_check() -> None:
    """Fail import if the registry itself violates the PHI-free rule (defense in depth — the
    PropSpec constructor already enforces most of this)."""
    for name, spec in REGISTRY.items():
        for key, pspec in spec.props.items():
            if pspec.type is PropType.ENUM and not pspec.values:
                raise ValueError(f"{name}.{key}: ENUM property with no values")
    overlap = set(REGISTRY) & RESERVED_FUTURE_NAMES
    if overlap:
        raise ValueError(f"reserved future names collide with live events: {sorted(overlap)}")


_self_check()
