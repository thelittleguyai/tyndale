"""Per-line-item example scenarios (Phase 2L / Brock feedback 2).

Deterministic category → "what a typical patient would have experienced" mapper.
It guarantees the encounter-verification UI always has example scenarios even on
the no-real-Claude path (fixtures + dev), and serves as the backfill when the
Bill Detective translate pass doesn't supply them.

When real Claude runs translate mode, it produces richer per-item scenarios
guided by the Skill (intelligence-layer/.../06_encounter_verification/
lineitem_plain_language.md §"Example scenarios per category"). This module is
the floor, not the ceiling.

HARD LINE (refusals.md / L07): scenarios describe what HAPPENED — factual,
second-person, past tense ("You'd typically have...") — NEVER a clinical
judgment about whether a service should have happened or was necessary.
"""

from __future__ import annotations

# Per-category scenario sets. 3-5 each (generic gets 3) — more than 5 starts to
# feel like a checklist and pressures false confirmations.
_ER_EM = [
    "You'd typically have spent at least one to two hours in the ER",
    "You'd have been seen by multiple staff — usually a nurse first, then a doctor",
    "You'd likely have had tests done, like blood work or imaging",
    "You may have had IV fluids or medications given",
    "You may have been monitored for a stretch before being sent home or admitted",
]
_EM = [
    "You'd typically have spent somewhere from a few minutes to about an hour at the visit",
    "You'd have been seen by one or more staff — often a nurse, then a provider",
    "You'd have answered questions about your symptoms and history",
    "You may have had tests done or a physical exam",
]
_LAB = [
    "You'd have had a sample taken — usually a blood draw from your arm",
    "The sample was sent to a lab rather than analyzed in the room with you",
    "You'd typically have gotten the results within a few days, often by patient portal or a follow-up call",
]
_IMAGING = [
    "You'd have had a specific body part scanned",
    "You'd have been asked to stay still, and sometimes to hold your breath",
    "Your scan would have taken anywhere from a few minutes to about an hour",
    "You may have had contrast dye given by IV or had to drink it",
    "You'd typically have changed into a gown",
]
_PROCEDURE = [
    "You'd have had some form of numbing or anesthesia — local or general",
    "You'd have had an incision, instrument, or device used",
    "You'd have spent time in a recovery area afterward",
    "You may have been given follow-up instructions or a return visit",
]
_INJECTION = [
    "You'd have had a shot or an IV — often in your arm",
    "You may have felt a brief sting or pressure",
    "You'd typically have been sent home shortly after, sometimes after a short wait",
]
_SUPPLY = [
    "You'd have received a physical item or piece of equipment",
    "You may have been fitted for it or shown how to use it",
    "You'd typically have taken it home or had it delivered",
]
_GENERIC = [
    "You'd have interacted with a provider, facility, or service tied to this charge",
    "You may have received care, a test, or an item during the visit",
    "You'd typically remember at least part of it — if none of this sounds familiar, that's worth flagging",
]

_BY_CATEGORY = {
    "er_em": _ER_EM,
    "em": _EM,
    "lab": _LAB,
    "imaging": _IMAGING,
    "procedure": _PROCEDURE,
    "injection": _INJECTION,
    "supply": _SUPPLY,
    "unknown": _GENERIC,
}


def _category(code: str, code_system: str) -> str:
    c = (code or "").strip().upper()
    cs = (code_system or "CPT").upper()
    if not c:
        return "unknown"
    # HCPCS Level II / letter-prefixed codes.
    if cs == "HCPCS" or c[0].isalpha():
        letter = c[0]
        if letter == "E":
            return "supply"  # E-codes: DME
        if letter in ("J", "G"):
            return "injection"  # J: drugs; G0008/G0009: vaccine admin
        return "unknown"
    digits = "".join(ch for ch in c if ch.isdigit())
    if len(digits) < 4:
        return "unknown"
    n = int(digits[:5])
    if 99281 <= n <= 99288:
        return "er_em"
    if 99202 <= n <= 99499:
        return "em"
    if 70000 <= n <= 79999:
        return "imaging"
    if 80000 <= n <= 89999:
        return "lab"
    if (90281 <= n <= 90399) or (90460 <= n <= 90761) or (96360 <= n <= 96549):
        return "injection"
    if 10000 <= n <= 69999:
        return "procedure"
    return "unknown"


def scenarios_for(code: str, code_system: str = "CPT") -> list[str]:
    """3-5 factual, second-person, past-tense example scenarios for the code's
    service category. Unknown codes get a minimal (3) generic set rather than
    fabricated specifics."""
    return list(_BY_CATEGORY[_category(code, code_system)])


def backfill_scenarios(items: list[dict]) -> list[dict]:
    """Ensure every line-item dict carries example_scenarios. Fills any item
    that lacks them (translate pass didn't supply them, or a pre-2L stored row)
    from the deterministic category mapper. Mutates in place + returns the list."""
    for it in items:
        if not it.get("example_scenarios"):
            it["example_scenarios"] = scenarios_for(it.get("code", ""), it.get("code_system", "CPT"))
    return items
