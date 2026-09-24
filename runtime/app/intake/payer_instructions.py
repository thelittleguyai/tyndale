"""The payer-instructions corpus (doc 40 §A5) — "Help me find it", from the insurer's own site.

Keyed by (payer_id × document_type × screen_id). Phase 2 ingests
``docs/research/portal_navigation_guide_2026-07-02.md`` (guided Phase 2, item G): nine payers —
UnitedHealthcare, Elevance/Anthem, Aetna, Cigna, Kaiser, Centene/Ambetter, HCSC (BCBS
IL/TX/OK/NM/MT), Florida Blue, Highmark — the BCBS router, and the no-card registration branch.

The guide's ship rule is this module's rule: **a payer path is rendered only when it was VERIFIED**
(against the payer's own public pages, 2026-07-02). Everything the guide marks UNVERIFIED — the
exact in-portal sub-menu labels, two payers' registration fields, two app names, the pharmacy
split — is STORED here with ``verified=False`` so the hands-on pass (test accounts, pre-launch)
knows what to fill, and it is NEVER rendered: the generic steps show instead. Portals change, so
every entry carries ``verified_on`` and Admin › Knowledge says when the quarterly re-verify is due.

What renders is registry copy (``intake.help.*`` — drift-guarded, graded ≤ 5.9, PROPOSED for
Brock in the v2 DRAFT); the FACTS behind it are data here. A payer's verified front door (its
sign-in line) replaces the generic "sign in to your insurer's website" step even where its menu
labels are unverified — a verified fact, followed by the general steps.

The receiving dock from Phase 1 stays: ``intelligence-layer/reference/payer_instructions/*.json``
(Brock's or QA's verbatim steps) — absent directory = no-op, a bad file is rejected WHOLE and by
name, never half-applied, and a malformed drop can never break the runtime. A dropped entry
overrides the built-in one for the same key; an unverified one is stored and never rendered.

"Help me find it" is sendable by EMAIL through the one existing send path (users leave the app to
go to the portal — locked 5c). SMS is not built and is not offered. **No screen ever collects a
Social Security number**: the no-card branch only SAYS which payers accept one on their own site.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

DOCUMENT_TYPES: tuple[str, ...] = (
    "eob", "sbc", "insurance_card", "itemized_bill", "accumulators", "plan_year",
)  # fmt: skip
GENERIC = "generic"
_DIR = "reference/payer_instructions"
_MAX_STEPS = 8
_MAX_STEP_CHARS = 240

GUIDE = "docs/research/portal_navigation_guide_2026-07-02.md"
GUIDE_VERIFIED_ON = "2026-07-02"
GUIDE_SOURCE = "the payer's own public pages (portal guide, 2026-07-02)"
REVERIFY_EVERY_MONTHS = 3  # the guide: "re-verify quarterly (portals change)"

# (document_type) -> the generic steps, as registry keys — the guide's four-step pattern (first
# page → the Benefits / Coverage / My Plan menu → the documents list → sign-up prep), reconciled
# with the Phase 1 seeds. One generic entry serves every screen that asks for that document type.
SIGN_UP = "intake.help.sign_up"
GENERIC_STEP_KEYS: dict[str, tuple[str, ...]] = {
    "eob": (*(f"intake.help.eob_{n}" for n in range(1, 6)), SIGN_UP),
    "sbc": ("intake.help.sbc_1", "intake.help.sbc_2", "intake.help.sbc_5", "intake.help.sbc_3",
            "intake.help.sbc_4", SIGN_UP),
    "insurance_card": (*(f"intake.help.insurance_card_{n}" for n in range(1, 4)), SIGN_UP),
    "itemized_bill": tuple(f"intake.help.itemized_bill_{n}" for n in range(1, 5)),
    "accumulators": ("intake.help.accumulators_1", "intake.help.accumulators_2",
                     "intake.help.accumulators_4", "intake.help.accumulators_3", SIGN_UP),
    "plan_year": tuple(f"intake.help.plan_year_{n}" for n in range(1, 4)),
}  # fmt: skip
assert set(GENERIC_STEP_KEYS) == set(DOCUMENT_TYPES)
# the generic "Sign in to your insurer's website or app." — a known payer's own door replaces it
GENERIC_SIGN_IN_KEYS = frozenset({"intake.help.eob_1", "intake.help.sbc_1", "intake.help.accumulators_1"})
# the sheets that send someone to the payer's portal (the no-card and BCBS lines belong there)
PORTAL_DOCS = frozenset({"eob", "sbc", "insurance_card", "accumulators"})
BCBS_LOOKUP = "intake.help.bcbs_lookup"
BCBS_LOOKUP_PREFIX = "intake.help.bcbs_lookup_prefix"  # in-app only: never in an email (DL-47)


@dataclass(frozen=True)
class Payer:
    payer_id: str
    name: str  # "These steps are for {payer}."
    sign_in: str  # registry key: the verified front door (portal, app, quirk)
    no_card: str | None = None  # registry key: what signing up WITHOUT the card takes (verified)
    blue: bool = False  # a Blue Cross Blue Shield company (the BCBS router can land here)


PAYERS: dict[str, Payer] = {
    p.payer_id: p
    for p in (
        Payer("uhc", "UnitedHealthcare", "intake.help.uhc_sign_in", no_card="intake.help.uhc_no_card"),
        Payer("anthem", "Anthem", "intake.help.anthem_sign_in", blue=True),
        Payer("aetna", "Aetna", "intake.help.aetna_sign_in", no_card="intake.help.aetna_no_card"),
        Payer("cigna", "Cigna", "intake.help.cigna_sign_in"),
        Payer("kaiser", "Kaiser Permanente", "intake.help.kaiser_sign_in"),
        Payer("ambetter", "Ambetter", "intake.help.ambetter_sign_in", no_card="intake.help.ambetter_no_card"),
        Payer("hcsc", "Blue Cross and Blue Shield", "intake.help.hcsc_sign_in",
              no_card="intake.help.hcsc_no_card", blue=True),
        Payer("florida_blue", "Florida Blue", "intake.help.florida_blue_sign_in", blue=True),
        Payer("highmark", "Highmark", "intake.help.highmark_sign_in", blue=True),
    )
}


@dataclass(frozen=True)
class PayerEntry:
    payer_id: str
    payer_name: str
    document_type: str
    screen_id: str | None  # None = every screen that asks for this document type
    steps: tuple[str, ...] = ()  # verbatim text — a receiving-dock drop (Brock's / QA's words)
    source: str = "unspecified"  # a public help page vs a logged-in screen
    verified: bool = False  # the guide's ship rule: False is STORED and NEVER rendered
    verified_on: str | None = None  # ISO date; the quarterly re-verify runs off it
    step_keys: tuple[str, ...] = ()  # registry keys — the built-in corpus
    claim: str = ""  # the guide's own words for the fact (or what is still missing)

    @property
    def renderable(self) -> bool:
        return self.verified and bool(self.steps or self.step_keys)


def _v(payer_id: str, doc: str, keys: tuple[str, ...], claim: str) -> PayerEntry:
    return PayerEntry(payer_id, PAYERS[payer_id].name, doc, None, source=GUIDE_SOURCE, verified=True,
                      verified_on=GUIDE_VERIFIED_ON, step_keys=keys, claim=claim)


def _unverified(payer_id: str, doc: str, claim: str) -> PayerEntry:
    return PayerEntry(payer_id, PAYERS[payer_id].name, doc, None, source=GUIDE, claim=claim)


_TALLY = "intake.help.accumulators_3"  # "Write down the amount you have paid so far, and the date it shows."
_OPEN_SBC = "intake.help.sbc_3"  # "Open the file named Summary of Benefits and Coverage. Save it."
_AT_WORK = "intake.help.sbc_4"
_LABELS = "exact in-portal sub-menu label for the {what} (guide: UNVERIFIED)"

# The guide, ingested. Verified entries render; unverified ones are the hands-on pass's list.
CORPUS: tuple[PayerEntry, ...] = (
    # UnitedHealthcare — myuhc.com / UHC app; uhc.com/sign-in routes by plan type
    _v("uhc", "sbc", ("intake.help.uhc_sign_in", "intake.help.uhc_sbc", _OPEN_SBC, _AT_WORK, SIGN_UP),
       'Signed-in section "Coverage & Benefits"; SBC/COC viewable after sign-in'),
    _v("uhc", "accumulators", ("intake.help.uhc_sign_in", "intake.help.uhc_accumulators", _TALLY, SIGN_UP),
       '"view plan spending" = deductible tracking'),
    _unverified("uhc", "sbc", _LABELS.format(what="document list")),
    _unverified("uhc", "accumulators", _LABELS.format(what="deductible tracker")),
    # Elevance / Anthem — anthem.com / Sydney Health; deductible status on the app home
    _v("anthem", "accumulators", ("intake.help.anthem_sign_in", "intake.help.anthem_accumulators", _TALLY, SIGN_UP),
       "Deductible/copay status displayed on the app home"),
    _unverified("anthem", "sbc", _LABELS.format(what="document list")),
    _unverified("anthem", "accumulators", _LABELS.format(what="deductible tracker")),
    # Aetna — member.aetna.com / Aetna Health; the Medicare login page catches commercial users
    _v("aetna", "accumulators", ("intake.help.aetna_sign_in", "intake.help.aetna_accumulators", _TALLY, SIGN_UP),
       '"Benefit balances and plan limits" on the secure site'),
    _unverified("aetna", "sbc", _LABELS.format(what="document list") + " — plan documents are behind login"),
    _unverified("aetna", "accumulators", _LABELS.format(what="deductible tracker")),
    _unverified("aetna", "eob", "pharmacy may sit in CVS Caremark (guide: unverified; pharmacy-portal split matrix)"),
    # Cigna — myCigna; "Your Plan at a Glance"; a public no-login SBC library for individual plans
    _v("cigna", "sbc", ("intake.help.cigna_sbc_public", "intake.help.cigna_sbc_work", _OPEN_SBC, SIGN_UP),
       "Public no-login SBC library for individual/family plans (cigna.com → member guide → Plan "
       "Documents); employer members use myCigna or HR"),
    _v("cigna", "accumulators", ("intake.help.cigna_sign_in", "intake.help.cigna_accumulators", _TALLY, SIGN_UP),
       'dashboard = "Your Plan at a Glance" with deductible remaining, YTD in/out-of-network '
       "deductibles + OOP with progress bars"),
    _unverified("cigna", "insurance_card", "registration field requirements (guide: UNVERIFIED)"),
    # Kaiser Permanente — kp.org; exact verified paths; region picker; external portals are normal
    _v("kaiser", "sbc", ("intake.help.kaiser_sign_in", "intake.help.kaiser_sbc", _OPEN_SBC,
                         "intake.help.kaiser_elsewhere", SIGN_UP),
       'sign in → Benefits → "View benefit summary" / "Coverage documents"'),
    _v("kaiser", "accumulators", ("intake.help.kaiser_sign_in", "intake.help.kaiser_accumulators",
                                  "intake.help.kaiser_accumulators_billing", _TALLY,
                                  "intake.help.kaiser_elsewhere", SIGN_UP),
       'Benefits → "Track the progress of your plan" (+ Billing → "View your out-of-pocket summary" on '
       "some plans)"),
    _unverified("kaiser", "insurance_card", "registration field requirements (guide: UNVERIFIED)"),
    # Centene / Ambetter — one central member login; ignore the 29 state-branded sites
    _unverified("ambetter", "sbc", _LABELS.format(what="document list")),
    _unverified("ambetter", "accumulators", _LABELS.format(what="deductible tracker")),
    # HCSC (BCBS IL/TX/OK/NM/MT) — Blue Access for Members; the card is required to register
    _v("hcsc", "accumulators", ("intake.help.hcsc_sign_in", "intake.help.hcsc_accumulators", _TALLY, SIGN_UP),
       '"Check your deductible" in BAM'),
    _unverified("hcsc", "sbc", _LABELS.format(what="document list")),
    _unverified("hcsc", "accumulators", _LABELS.format(what="deductible tracker")),
    _unverified("hcsc", "insurance_card", "the HCSC app name (guide: UNVERIFIED)"),
    # Florida Blue — floridablue.com; plan details show deductibles and claims
    _v("florida_blue", "accumulators", ("intake.help.florida_blue_sign_in", "intake.help.florida_blue_accumulators",
                                        _TALLY, SIGN_UP),
       '"View plan details like deductibles and claims" after login'),
    _unverified("florida_blue", "sbc", _LABELS.format(what="document list") + " — the public Member Forms library is forms"),
    _unverified("florida_blue", "accumulators", _LABELS.format(what="deductible tracker")),
    _unverified("florida_blue", "insurance_card", "the Florida Blue app name (guide: UNVERIFIED)"),
    # Highmark — member.myhighmark.com / My Highmark (one login, web + app); deductibles in-app
    _v("highmark", "accumulators", ("intake.help.highmark_sign_in", "intake.help.highmark_accumulators",
                                    _TALLY, SIGN_UP),
       "Deductibles in-app; My Highmark is the common front door"),
    _unverified("highmark", "sbc", _LABELS.format(what="document list") + " — the Forms Library is behind login"),
    _unverified("highmark", "accumulators", _LABELS.format(what="deductible tracker")),
)  # fmt: skip

# (payer_id, document_type, screen_id|None) -> entry. The corpus first, then the receiving dock.
PAYER_ENTRIES: dict[tuple[str, str, str | None], PayerEntry] = {}


# ── which payer is this? ─────────────────────────────────────────────────────────────────
_BLUE = re.compile(r"\bblue\s*(?:cross|shield|care)|\bbcbs|\bflorida\s*blue\b|\bblue\s+access\b", re.I)
_NOT_BLUE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uhc", re.compile(r"\bunited\s*health\s*care\b|\buhc\b", re.I)),
    ("aetna", re.compile(r"\baetna\b", re.I)),
    ("cigna", re.compile(r"\bcigna\b", re.I)),
    ("kaiser", re.compile(r"\bkaiser\b", re.I)),
    ("ambetter", re.compile(r"\bambetter\b|\bcentene\b", re.I)),
)
# The BCBS router's map (the guide): Anthem states → Anthem; IL/TX/OK/NM/MT → HCSC; FL → Florida
# Blue; PA/DE/WV/WNY → Highmark. It reads the PLAN NAME printed on the card, where each company
# names itself or its state. A company's own name wins over any state it serves — and a state
# alone places only a BLUE plan ("Texas Children's Health Plan" is not HCSC).
_BLUE_COMPANIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthem", re.compile(r"\banthem\b|\belevance\b", re.I)),
    ("highmark", re.compile(r"\bhighmark\b", re.I)),
    ("florida_blue", re.compile(r"\bflorida\s*blue\b", re.I)),
    ("hcsc", re.compile(r"\bhcsc\b|\bhealth\s+care\s+service\s+corp", re.I)),
)
_BLUE_STATES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("florida_blue", re.compile(r"\bflorida\b|\bbcbs\s*fl\b", re.I)),
    ("hcsc", re.compile(r"\billinois\b|\btexas\b|\boklahoma\b|\bnew\s+mexico\b|\bmontana\b|"
                        r"\bbcbs\s*(?:il|tx|ok|nm|mt)\b", re.I)),
    ("highmark", re.compile(r"\bpennsylvania\b|\bdelaware\b|\bwest\s+virginia\b|\bwestern\s+new\s+york\b|"
                            r"\bbcbs\s*(?:pa|de|wv)\b", re.I)),
)
# words that say nothing about WHICH Blue: a name made only of these needs the router question
_BLUE_FILLER = frozenset(
    "blue cross shield bluecross blueshield bcbs bcbsa care and of the plan plans health healthcare "
    "insurance company co inc llc association assn ppo hmo epo pos network member members card".split()
)


def payer_id_for(name: str | None) -> str | None:
    """'UnitedHealthcare of Texas, Inc.' -> 'unitedhealthcare_of_texas_inc'. A stable slug for the
    receiving dock's files (which may also list aliases). None when there is no name."""
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug or None


def is_blue(name: str | None) -> bool:
    return bool(name and _BLUE.search(name))


def _first(routes: tuple[tuple[str, re.Pattern[str]], ...], name: str) -> str | None:
    return next((pid for pid, rx in routes if rx.search(name)), None)


def route_blue(plan_name: str | None) -> str | None:
    """The BCBS router: the plan name on the card → the Blue company whose portal it is, or None
    (every other Blue — generic steps plus the bcbs.com lookup). The answer is about a Blue plan
    by construction, so a state alone places it."""
    if not plan_name:
        return None
    return _first(_BLUE_COMPANIES, plan_name) or _first(_BLUE_STATES, plan_name)


def blue_is_generic(name: str | None) -> bool:
    """A Blue name that does not say WHICH company ("Blue Cross Blue Shield", "BCBS PPO") — the
    only case the router question is asked. "Premera Blue Cross" names its company: no question,
    it just is not one the guide covers."""
    words = re.findall(r"[a-z]+", (name or "").lower())
    return is_blue(name) and all(w in _BLUE_FILLER for w in words)


def match_payer(name: str | None) -> str | None:
    """A payer name as a card, bill or EOB prints it (or the user typed it) → the corpus payer."""
    if not name:
        return None
    # "Anthem" alone and "Highmark" alone name their company; a state places only a Blue plan
    return _first(_NOT_BLUE, name) or _first(_BLUE_COMPANIES, name) or (
        _first(_BLUE_STATES, name) if is_blue(name) else None
    )


def needs_blue_router(payer_name: str | None) -> bool:
    """The card or bill says Blue Cross / Blue Shield and not which company (the planner's
    `blue_plan` screen)."""
    return blue_is_generic(payer_name) and match_payer(payer_name) is None


@dataclass(frozen=True)
class HelpContext:
    """What "Help me find it" may know about this case — read from the case, never asked for."""

    payer_name: str | None = None  # coverage.payer_name, as a document or the user gave it
    blue_plan_name: str | None = None  # the BCBS router's answer
    id_prefix: str | None = None  # the router's "first 3 letters of your member ID" (in-app only)
    card_on_file: bool = True
    card_skipped: bool = False  # "I don't have my card"

    @property
    def payer_id(self) -> str | None:
        return match_payer(self.payer_name) or (
            route_blue(self.blue_plan_name) if is_blue(self.payer_name) else None
        )

    @property
    def unplaced_blue(self) -> bool:
        """A Blue plan the corpus cannot place — the guide's "else": generic + the bcbs.com lookup."""
        return is_blue(self.payer_name) and self.payer_id is None

    def display_name(self, payer_id: str) -> str:
        if payer_id == "hcsc":  # five states' companies share one portal: say the user's own
            return (self.blue_plan_name or self.payer_name or PAYERS["hcsc"].name)[:80]
        return PAYERS[payer_id].name if payer_id in PAYERS else payer_id


# ── the receiving dock ───────────────────────────────────────────────────────────────────
def _corpus_dir() -> Path:
    override = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
    root = Path(override).resolve() if override else Path(__file__).resolve().parents[3] / "intelligence-layer"
    return root / _DIR


def _validate(raw: dict, *, file: str) -> list[PayerEntry]:
    payer_name = str(raw.get("payer_name") or "").strip()
    payer_id = payer_id_for(raw.get("payer_id") or payer_name)
    if not payer_id or not payer_name:
        raise ValueError("payer_id / payer_name missing")
    out: list[PayerEntry] = []
    ids = [payer_id, *[x for a in raw.get("aliases") or [] if (x := payer_id_for(a))]]
    for e in raw.get("entries") or []:
        doc = e.get("document_type")
        if doc not in DOCUMENT_TYPES:
            raise ValueError(f"unknown document_type {doc!r}")
        steps = [str(s).strip() for s in e.get("steps") or [] if str(s).strip()]
        if not 1 <= len(steps) <= _MAX_STEPS:
            raise ValueError(f"{doc}: needs 1–{_MAX_STEPS} steps, got {len(steps)}")
        if any(len(s) > _MAX_STEP_CHARS for s in steps):
            raise ValueError(f"{doc}: a step is over {_MAX_STEP_CHARS} characters")
        verified_on = e.get("verified_on") or e.get("as_of") or raw.get("verified_on") or raw.get("as_of")
        if verified_on:
            datetime.date.fromisoformat(str(verified_on))  # a bad date rejects the file
        for pid in ids:
            out.append(
                PayerEntry(
                    payer_id=pid,
                    payer_name=payer_name,
                    document_type=doc,
                    screen_id=e.get("screen_id") or None,
                    steps=tuple(steps),
                    source=str(e.get("source") or "unspecified"),
                    verified=bool(e.get("verified", False)),
                    verified_on=str(verified_on) if verified_on else None,
                )
            )
    if not out:
        raise ValueError("no entries")
    return out


def load_payer_entries(
    target: dict[tuple[str, str, str | None], PayerEntry] | None = None,
) -> dict[tuple[str, str, str | None], PayerEntry]:
    table = PAYER_ENTRIES if target is None else target
    if target is None:
        # the corpus: a verified entry holds its key; an unverified one never displaces it
        for x in CORPUS:
            key = (x.payer_id, x.document_type, x.screen_id)
            if x.verified or key not in table:
                table[key] = x
    d = _corpus_dir()
    if not d.is_dir():
        return table  # nothing dropped — the corpus and the generic steps serve everyone
    for f in sorted(d.glob("*.json")):
        try:
            staged = _validate(json.loads(f.read_text(encoding="utf-8")), file=f.name)
        except Exception as e:  # noqa: BLE001 — a bad drop is rejected whole, never half-applied
            log.error("payer_instructions.file_rejected", file=f.name, error=str(e))
            continue
        table.update({(x.payer_id, x.document_type, x.screen_id): x for x in staged})
    return table


# ── what "Help me find it" shows ─────────────────────────────────────────────────────────
def _entry(payer_id: str, document_type: str, screen_id: str | None) -> PayerEntry | None:
    for key in ((payer_id, document_type, screen_id), (payer_id, document_type, None)):
        e = PAYER_ENTRIES.get(key)
        if e is not None and e.renderable:  # the ship rule: an unverified path is never shown
            return e
    return None


def instructions_for(
    document_type: str, screen_id: str | None = None, ctx: HelpContext | None = None
) -> dict | None:
    """The payer's own verified path when the payer is known and the corpus has one
    (screen-specific first), else the generic steps — behind the payer's own front door when that
    is known. Then the no-card line (on "I don't have my card") and, for a Blue the corpus cannot
    place, the bcbs.com lookup. None for an unknown document type."""
    if document_type not in DOCUMENT_TYPES:
        return None
    ctx = ctx or HelpContext()
    pid = ctx.payer_id
    payer = PAYERS.get(pid) if pid else None
    entry = _entry(pid, document_type, screen_id) if pid else None
    if entry is not None:
        out = {
            "scope": "payer",
            "payer_id": pid,
            "payer_name": ctx.display_name(pid) if entry.step_keys else entry.payer_name,
            "steps": list(entry.steps),
            "step_keys": list(entry.step_keys),
            "source": entry.source,
            "verified": True,
            "verified_on": entry.verified_on,
        }
    else:
        keys = list(GENERIC_STEP_KEYS[document_type])
        if payer and keys[0] in GENERIC_SIGN_IN_KEYS:
            keys[0] = payer.sign_in  # a verified fact: this payer's own door, general steps after it
        out = {"scope": GENERIC, "payer_id": pid, "payer_name": None, "steps": [], "step_keys": keys,
               "source": "generic", "verified": True, "verified_on": None}
    if document_type in PORTAL_DOCS:
        # "I don't have my card" (the card's own sheet asks the same question): what signing up
        # without it takes at THIS payer. Tyndale never asks for the number itself.
        if payer and payer.no_card and not ctx.card_on_file and (ctx.card_skipped or document_type == "insurance_card"):
            out["step_keys"].append(payer.no_card)
        if ctx.unplaced_blue:
            out["step_keys"].append(BCBS_LOOKUP)
    return out


def _add_months(d: datetime.date, months: int) -> datetime.date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    last = (datetime.date(year + month // 12, month % 12 + 1, 1) - datetime.timedelta(days=1)).day
    return datetime.date(year, month, min(d.day, last))


def reverify_due(verified_on: str | None) -> str | None:
    """The quarterly re-verify date for an entry verified on `verified_on` (ISO)."""
    if not verified_on:
        return None
    return _add_months(datetime.date.fromisoformat(verified_on), REVERIFY_EVERY_MONTHS).isoformat()


load_payer_entries()
