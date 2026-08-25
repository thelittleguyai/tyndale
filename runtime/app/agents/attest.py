"""Attest-and-proceed (Brock July 16 §A2 state 1 — COMPLIANCE; first brick of the D2 spine).

When the extracted patient name doesn't fuzzy-match the account holder's profile name, the
thread enters ``attest_required`` BEFORE encounter verification: a relationship menu
(self / spouse-partner / my child / parent-relative I assist / other-authorized), a confirm
line, and a decline path that closes the flow gracefully (case → ``attest_declined``, honest
message, no audit). Every attestation AND decline persists to the audit log as an
``attestation`` event through the encrypted envelope — the persistence IS the compliance
point.

Event shape (coordinate with the D2 attest/authorization design doc — the doc is not yet
in-repo, so this encodes exactly the fields Brock's §3 spec names, nothing more):
    {action, relationship, patient_name_as_extracted, patient_deceased} +
    the envelope's own user_id / case_file_id / timestamp / actor.

Matching is deliberately asymmetric-conservative: a mismatch only triggers when BOTH names
are present and disagree — missing data never fabricates a mismatch (and never silently
skips one that's visible). "AMY E FLUEGEL" vs "Amy Fluegel" is a MATCH (middle initials,
case, and punctuation are noise, per the worked example).
"""

from __future__ import annotations

import datetime
import re

from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.sources.extraction import grep_patient_name

# Brock's §3.1 relationship menu — SEVEN options, in his render order. Each maps 1:1 onto a
# registry copy key (attest.menu_<key>). Note there is deliberately no "self" option (a name
# mismatch means the bill isn't the account holder's) and no "none of the above, but let me
# in" escape (conformance checklist F1) — refusing is the decline path, not a menu entry.
RELATIONSHIPS = (
    "spouse_partner",
    "parent_guardian",
    "adult_child_caregiver",
    "healthcare_poa",
    "court_guardian",
    "executor",
    "other",
)

_NAME_NOISE_RE = re.compile(r"[^a-z ]+")


def _name_tokens(raw: str | None) -> list[str]:
    """Lowercased word tokens with punctuation stripped and single-letter tokens (middle
    initials) dropped: "AMY E. FLUEGEL" → ["amy", "fluegel"]."""
    if not raw:
        return []
    cleaned = _NAME_NOISE_RE.sub(" ", raw.lower())
    return [t for t in cleaned.split() if len(t) > 1]


def names_match(a: str | None, b: str | None) -> bool | None:
    """Fuzzy-normalized comparison. None = cannot compare (either side missing/empty after
    normalization) — callers must treat that as NO mismatch, never as one."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return None
    if ta == tb or sorted(ta) == sorted(tb):
        return True
    # First + last agree (extra suffixes/compound middles are noise): compare the ends.
    if len(ta) >= 2 and len(tb) >= 2 and ta[0] == tb[0] and ta[-1] == tb[-1]:
        return True
    return False


def profile_name(user: User) -> str | None:
    parts = [p for p in ((user.first_name or "").strip(), (user.last_name or "").strip()) if p]
    return " ".join(parts) or None


def derive_patient_name(case: CaseFile) -> str | None:
    """The typed field, else the documents' structured patient fields, else a conservative
    grep of the OCR preview — the same structured-artifacts-only ladder as provider_name.
    Lets pre-0036 cases (Amy's Beloit case) evaluate on next open without a backfill run."""
    if case.patient_name:
        return case.patient_name
    docs = [d for d in (case.documents or []) if isinstance(d, dict)]
    typed = next((d["patient_name"] for d in docs if d.get("patient_name")), None)
    if typed:
        return str(typed)
    return next(
        (p for d in docs if (p := grep_patient_name(d.get("ocr_text_preview") or ""))), None
    )


def evaluate_attest_state(case: CaseFile, user: User) -> bool:
    """The trigger + BACKFILL GUARD: on any evaluation (extraction completion, thread
    reconcile, case open), a case whose extracted patient name mismatches the profile name
    and has no attestation yet flips to ``attest_status='required'`` — existing cases are
    never silently grandfathered. Returns True when the case now requires attestation.
    Mutates the ORM instance only; committing is the caller's job."""
    if case.attest_status in ("attested", "declined"):
        return False
    from app.sources.extraction import plausible_extracted_name

    patient = derive_patient_name(case)
    if not plausible_extracted_name(patient):
        # Bill-form furniture persisted before the extraction gate (the 2026-08-22 UMC
        # statement) is not a person — unknowable, and unknowable NEVER triggers attest.
        patient = None
    if patient and not case.patient_name:
        case.patient_name = patient  # persist the typed derivation (DL-39)
    match = names_match(patient, profile_name(user))
    required = match is False  # None (unknowable) never triggers
    if required and case.attest_status != "required":
        case.attest_status = "required"
    elif not required and case.attest_status == "required":
        # Name evidence changed (e.g. profile completed with the matching name) — release.
        case.attest_status = "not_required"
    return case.attest_status == "required"


def _patient_age(case: CaseFile) -> int | None:
    """Age from a TYPED extracted patient DOB if any document carries one (patient_dob,
    ISO date). No document field → None → the teen prompt never fires on a guess."""
    docs = [d for d in (case.documents or []) if isinstance(d, dict)]
    raw = next((d["patient_dob"] for d in docs if d.get("patient_dob")), None)
    if not raw:
        return None
    try:
        dob = datetime.date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
    today = datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def attest_edge_signals(case: CaseFile, *, patient_deceased: bool = False) -> list[str]:
    """§3's elevated edge cases, surfaced as PROMPTS (extra guidance), never blocks.
    Signals are typed-field seams: teen = extracted patient_dob puts the patient under 18;
    deceased = the user selected it in the menu. (A5, Brock 2026-08-18: the SUD signal is
    gone — his §3 authors teen + deceased only, and the script governs.)"""
    signals: list[str] = []
    age = _patient_age(case)
    if age is not None and age < 18:
        signals.append("teen")
    if patient_deceased:
        signals.append("deceased")
    return signals
