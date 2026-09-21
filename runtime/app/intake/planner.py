"""The Intake Planner (doc 40 §A4) — a planner, not a wizard.

CO-1A advanced through a FIXED list (``INTAKE_STEPS[idx + 1]``). This replaces it. After every
capture or answer the route rebuilds a snapshot of what the engine already knows
(``gather_inputs``), the planner turns it into a gap list over the five input groups
(``gap_list``), and the next screen is the first registry entry that still applies and is not
yet satisfied (``next_screen``). Nothing is asked that a document already answered.

Every signal is read from the seam that OWNS it — this module re-implements none of them:

  documents / types ........ case_files.documents (the classifier's verdict, never the user's intent)
  summary vs itemized ...... ingestion.bill_heuristics.detect_summary_bill
  wrong document ........... agents.wrongdoc.classify_wrong_document
  cost-share inputs ........ sources.missing_data_priors.missing_cost_share_inputs over
                             sources.plan_docs.merge_case_coverage (case wins, plan SBC fills)
  SBC on file .............. sources.plan_docs.plan_sbc_state
  Plan Library candidate ... services.plan_library.match (the CO-12C propose/confirm path)
  population ............... sources.regime_detection.detect_regime (via case.regime_detection)
  EOB completeness ......... sources.eob_completeness.summarize_eob_completeness
  attest ................... agents.attest.evaluate_attest_state (case.attest_status)
  encounter facts .......... case_files.line_items — ONE card per item the engine emitted

SILENT vs ASK (§A4, last paragraph) is the EXISTING ladder, not a new rule: an input is
load-bearing when its plausible spread is material at the USER_CHASE bar —
``materiality.is_material(prior.usd_span(), prior.high, USER_CHASE)`` over
``missing_data_priors.MISSING_DATA_PRIORS`` — exactly the test ``orchestrator._compute_disclosure``
uses to build ``chase_inputs`` (disclosure tier 3). Below the bar the audit defaults it silently
(tier 0–1) and the planner never raises a screen for it.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from app.plan_types import COMMERCIAL_FAMILY, PLAN_TYPES
from app.sources.materiality import USER_CHASE, is_material
from app.sources.missing_data_priors import MISSING_DATA_PRIORS, REQUIRED_COST_SHARE_INPUTS

InputGroup = Literal["claim", "plan_rules", "accumulators", "patient_context", "encounter_facts"]
INPUT_GROUPS: tuple[str, ...] = (
    "claim",
    "plan_rules",
    "accumulators",
    "patient_context",
    "encounter_facts",
)

# The seven progress segments (§A8), in display order, and the input group each belongs to.
PROGRESS_GROUPS: tuple[str, ...] = (
    "bill",
    "card",
    "plan_rules",
    "eob",
    "timeline",
    "about_you",
    "confirmations",
)

READY = "READY"

# Phase 1 runs the COMMERCIAL route only. Employer-shaped governmental plans (FEHB/PSHB, state and
# local) carry the same documents — an SBC, EOBs, a plan year — so they ride it too. Everything
# else exits with one honest line to the chat-first flow, which already carries MSNs and the rest.
# regime -> the population enum (doc 40 §A4-4's seven, plus "other" for plans that are not full
# insurance). The handoff analytics event carries this enum, never the regime's detail.
POPULATION_OF_REGIME: dict[str, str] = {
    "state_regulated_commercial": "commercial",
    "erisa_self_funded": "commercial",
    "fehb_pshb": "commercial",
    "nonfederal_governmental": "commercial",
    "medicare_traditional": "medicare",
    "medicare_advantage": "medicare_advantage",
    "medicaid_ffs": "medicaid",
    "medicaid_mco": "medicaid",
    "dual_eligible": "dual",
    "self_pay": "self_pay",
    "tricare": "tricare_va",
    "va_champva": "tricare_va",
    "stldi": "other",
    "excepted_coverage": "other",
}
assert set(POPULATION_OF_REGIME) == set(PLAN_TYPES), "every regime needs a population"
assert all(POPULATION_OF_REGIME[r] == "commercial" for r in COMMERCIAL_FAMILY)

POPULATIONS: tuple[str, ...] = (
    "commercial",
    "medicare",
    "medicare_advantage",
    "medicaid",
    "dual",
    "self_pay",
    "tricare_va",
    "other",
)

BILL_TYPES = frozenset({"bill", "itemized_bill"})
EOB_TYPES = frozenset({"eob", "ma_eob", "msn", "tricare_eob"})
CARD_TYPES = frozenset({"insurance_card"})
SBC_TYPES = frozenset({"sbc", "plan_summary"})


# ── the snapshot ─────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PlannerInputs:
    """Everything the planner may look at, already read from the owning seams. Frozen and
    plain so every rule is a unit test with no database."""

    # claim
    bill_count: int = 0
    bill_is_summary: bool = False
    eob_count: int = 0
    card_present: bool = False
    wrong_document: str | None = None  # wrongdoc branch when documents exist but none is auditable
    payer_known: bool = False
    member_id_known: bool = False
    provider: str | None = None
    date_of_service: datetime.date | None = None
    billed_total: float | None = None
    patient_name: str | None = None
    # plan rules
    sbc_on_file: bool = False
    plan_proposal: bool = False
    # an EMPTY case is missing all of them — the default must not read as "rules known"
    missing_cost_share: tuple[str, ...] = REQUIRED_COST_SHARE_INPUTS
    coverage: dict = field(default_factory=dict)  # EFFECTIVE coverage (case over plan SBC)
    # population — a VERIFIED detection (high-confidence documents or a user confirm), or the
    # plain-language answer to the coverage-type ask. None = not known yet: the planner asks.
    population: str | None = None
    regime: str | None = None
    regime_candidate: str | None = None
    # accumulators
    plan_year_start: str | None = None  # ISO date; from the SBC coverage period or the ask
    plan_year_source: str | None = None  # "sbc" | "user"
    eobs_undated: int = 0
    completeness_confirmed: bool | None = None
    deductible_met_known: bool = False
    oop_met_known: bool = False
    # patient context
    attest_status: str = "not_required"
    secondary_answered: bool = False
    # encounter facts
    line_items: int = 0
    confirmations_done: bool = False
    case_status: str = "open"
    # what the user has already told the planner (case_files.intake_state)
    skipped: frozenset[str] = frozenset()
    acked: frozenset[str] = frozenset()

    @property
    def on_guided_route(self) -> bool:
        """Unknown stays on the route — the planner ASKS rather than guess (§A4-1)."""
        return self.population in (None, "commercial")

    @property
    def accumulators_resolved(self) -> bool:
        """The EOB stack answers "how much had you paid by then?" on its own: the user
        confirmed it is ALL of them and every one carries a date the engine can place."""
        return (
            self.eob_count > 0
            and self.completeness_confirmed is True
            and self.eobs_undated == 0
        )


def population_of(regime: str | None) -> str | None:
    """The §A4-4 population a VERIFIED regime belongs to (None when there is no regime)."""
    return POPULATION_OF_REGIME.get(regime) if regime else None


def load_bearing(key: str, coverage: dict | None = None) -> bool:
    """Is this missing input worth ASKING for? The existing ladder decides (module docstring).

    Plan terms use their prior's plausible spread. An accumulator ("how much of the deductible
    had you met?") can swing the answer by at most the cap it counts toward — the known
    deductible / out-of-pocket max, else that cap's own prior."""
    cov = coverage or {}
    cap_of = {"deductible_met": "deductible_amount", "oop_max_met": "oop_max_amount"}
    if key in cap_of:
        cap_key = cap_of[key]
        cap = cov.get(cap_key)
        prior = MISSING_DATA_PRIORS.get(cap_key)
        if cap is not None:
            try:
                spread = float(cap)
            except (TypeError, ValueError):
                spread = 0.0
            return is_material(spread, spread, USER_CHASE)
        return bool(prior) and is_material(prior.usd_span(), prior.high, USER_CHASE)
    prior = MISSING_DATA_PRIORS.get(key)
    return bool(prior) and is_material(prior.usd_span(), prior.high, USER_CHASE)


# ── the gap list ─────────────────────────────────────────────────────────────────────────
GapState = Literal["resolved", "unresolved", "skipped", "not_needed"]


@dataclass(frozen=True)
class Gap:
    key: str
    group: InputGroup
    state: GapState
    provenance: str | None = None  # document | user | plan_library | detection | engine
    load_bearing: bool = True
    limits: str | None = None  # registry key: what leaving this unresolved costs the answer
    screen: str | None = None  # where the readiness "edit" link goes

    @property
    def open(self) -> bool:
        return self.state == "unresolved"


@dataclass(frozen=True)
class GapList:
    gaps: tuple[Gap, ...]
    population: str | None
    on_guided_route: bool

    def get(self, key: str) -> Gap | None:
        return next((g for g in self.gaps if g.key == key), None)

    def state(self, key: str) -> str | None:
        g = self.get(key)
        return g.state if g else None

    def open_keys(self) -> list[str]:
        return [g.key for g in self.gaps if g.open]

    def by_group(self, group: str) -> list[Gap]:
        return [g for g in self.gaps if g.group == group]


def _state(resolved: bool, skipped: bool = False, needed: bool = True) -> GapState:
    if not needed:
        return "not_needed"
    if resolved:
        return "resolved"
    return "skipped" if skipped else "unresolved"


def gap_list(i: PlannerInputs) -> GapList:
    """What the audit still needs, over the five input groups (§A4-2)."""
    sk, cov = i.skipped, i.coverage
    gaps: list[Gap] = []

    # 1 · claim — the bill, the insurer's statement, who the insurer is
    gaps.append(
        Gap("bill", "claim", _state(i.bill_count > 0, "bill" in sk), "document",
            limits="intake.limits.no_bill", screen="bill")
    )
    gaps.append(
        Gap("itemized_bill", "claim",
            _state(not i.bill_is_summary, "bill_itemized" in sk, needed=i.bill_count > 0),
            "document", limits="intake.limits.summary_bill", screen="bill_itemized")
    )
    gaps.append(
        Gap("eob", "claim", _state(i.eob_count > 0, "eob" in sk), "document",
            limits="intake.limits.no_eob", screen="eob")
    )
    # "which insurer?" is NEVER asked when a document already named it (§A4-3).
    gaps.append(
        Gap("payer", "claim", _state(i.payer_known, "insurer" in sk or "card" in sk),
            "document" if i.payer_known else None,
            limits="intake.limits.no_payer", screen="card" if not i.card_present else "insurer")
    )

    # 2 · plan rules — the SBC, or the Plan Library's copy of it
    rules_known = not [k for k in i.missing_cost_share if load_bearing(k, cov)]
    gaps.append(
        Gap("plan_rules", "plan_rules",
            _state(rules_known or i.sbc_on_file, "plan_rules" in sk),
            "document" if i.sbc_on_file else ("plan_library" if rules_known else None),
            limits="intake.limits.no_plan_rules", screen="plan_rules")
    )

    # 3 · accumulators — where the plan year starts, and what had been paid by the visit
    has_stack = i.eob_count > 0
    gaps.append(
        Gap("plan_year_start", "accumulators",
            _state(bool(i.plan_year_start), "plan_year" in sk), i.plan_year_source,
            limits="intake.limits.no_plan_year", screen="plan_year")
    )
    # Asked EVERY time there is a stack to count (locked 5d) — upload or API, no exceptions.
    gaps.append(
        Gap("eob_completeness", "accumulators",
            _state(i.completeness_confirmed is not None, needed=has_stack), "user",
            limits="intake.limits.incomplete_eobs", screen="timeline")
    )
    for key, known, screen in (
        ("deductible_met", i.deductible_met_known, "deductible_met"),
        ("oop_max_met", i.oop_met_known, "oop_met"),
    ):
        lb = load_bearing(key, cov)
        gaps.append(
            Gap(key, "accumulators",
                # the EOB stack answering it means the manual screen NEVER appears (§A4-3)
                _state(known or i.accumulators_resolved, screen in sk, needed=lb),
                "document" if i.accumulators_resolved else ("user" if known else None),
                load_bearing=lb, limits="intake.limits.no_accumulator", screen=screen)
        )

    # 4 · patient context — population, whose bill, a second plan
    gaps.append(
        Gap("coverage_type", "patient_context",
            _state(i.population is not None, "coverage_type" in sk),
            "detection" if i.regime else ("user" if i.population else None),
            limits="intake.limits.no_coverage_type", screen="coverage_type")
    )
    gaps.append(
        Gap("attestation", "patient_context",
            _state(i.attest_status in ("attested", "not_required"),
                   needed=i.attest_status != "declined"),
            "user", limits=None, screen="attest")
    )
    gaps.append(
        Gap("other_insurance", "patient_context",
            _state(i.secondary_answered, "other_insurance" in sk), "user",
            load_bearing=False, limits="intake.limits.no_other_insurance",
            screen="other_insurance")
    )

    # 5 · encounter facts — as many cards as the engine emitted; never capped, never padded
    gaps.append(
        Gap("encounter_facts", "encounter_facts",
            _state(i.confirmations_done, needed=i.line_items > 0), "engine",
            limits="intake.limits.no_confirmations", screen="confirmations")
    )
    return GapList(tuple(gaps), i.population, i.on_guided_route)


# ── the screen registry ──────────────────────────────────────────────────────────────────
# Registry keys a screen REUSES rather than duplicates (Brock's authored copy stays in one place).
TRUST = "upload_trust_microcopy"  # §1.2 — "Encrypted. Never sold. Used only for your audit." (§C10)
SUMMARY_COACHING = "dataquality_summary_not_itemized"  # §5.2 — carries the itemized request script

# intake.<group>.* key groups that are not screens (the drift test allows exactly these).
SUPPORT_GROUPS: tuple[str, ...] = (
    "chrome", "progress", "resume", "limits", "analysis", "unlock", "example", "help",
)  # fmt: skip


@dataclass(frozen=True)
class Screen:
    """One registry entry. Its COPY is every `intake.<id>.*` key in the orchestration script —
    derived, never listed twice — plus ``shared``: slots filled from an existing registry key."""

    id: str
    kind: str  # the client renderer: info | capture | coach | summary | choice | fields | ...
    progress_group: str | None  # one of PROGRESS_GROUPS, or None (welcome / readiness / exits)
    input_group: InputGroup | None
    asks: str  # one line: what this screen is FOR
    shared: tuple[tuple[str, str], ...] = ()  # (slot, existing registry key)
    example: str | None = None  # app.intake.examples key, when the screen asks for a thing
    help_doc: str | None = None  # payer_instructions document_type for "Help me find it"
    expect: str | None = None  # the /v1/upload expected_type this capture asks for
    skippable: bool = False
    variant_of: str | None = None  # a variant shares its parent's place in the order

    def key(self, slot: str) -> str:
        return f"intake.{self.id}.{slot}"


def _applies(screen_id: str, i: PlannerInputs, g: GapList) -> bool:  # noqa: PLR0911, PLR0912
    """Does this screen have anything to ask of THIS case right now?"""
    s = g.state
    if screen_id == "welcome":
        return i.bill_count == 0 and i.eob_count == 0 and "welcome" not in i.acked
    if screen_id == "handoff":
        return not i.on_guided_route
    if screen_id == "bill":
        return s("bill") == "unresolved"
    if screen_id == "bill_itemized":
        return s("itemized_bill") == "unresolved" and "bill_itemized" not in i.acked
    if screen_id == "bill_summary":
        # read-back + "other bills for this same visit?" — asked ONCE, after the bill lands (§C1)
        return i.bill_count > 0 and "bill_summary" not in i.acked
    if screen_id == "eob":
        return s("eob") == "unresolved"
    if screen_id == "card":
        # the card identifies the PLAN; when the bill/EOB already carried payer + member id,
        # "it's already on your bill" (§B7) — no ask
        return not i.card_present and not (i.payer_known and i.member_id_known) and "card" not in i.skipped
    if screen_id == "insurer":
        return s("payer") == "unresolved" and (i.card_present or "card" in i.skipped)
    if screen_id == "coverage_type":
        return s("coverage_type") == "unresolved"
    if screen_id == "plan_rules_confirm":
        return s("plan_rules") == "unresolved" and i.plan_proposal
    if screen_id == "plan_rules":
        return s("plan_rules") == "unresolved" and not i.plan_proposal
    if screen_id == "plan_year":
        return s("plan_year_start") == "unresolved"
    if screen_id == "timeline":
        return s("eob_completeness") == "unresolved"
    if screen_id == "deductible_met":
        return s("deductible_met") == "unresolved"
    if screen_id == "oop_met":
        return s("oop_max_met") == "unresolved"
    if screen_id == "attest":
        return i.attest_status == "required"
    if screen_id == "other_insurance":
        return s("other_insurance") == "unresolved"
    if screen_id == "reading":
        # a bill is in, the engine has not emitted its facts yet
        return i.bill_count > 0 and i.line_items == 0 and i.case_status in ("open", "in_progress")
    if screen_id == "facts_only":
        return s("encounter_facts") == "unresolved" and "facts_only" not in i.acked
    if screen_id == "confirmations":
        return s("encounter_facts") == "unresolved"
    if screen_id == "readiness":
        return "readiness" not in i.acked
    return False


SCREEN_REGISTRY: tuple[Screen, ...] = (
    Screen("welcome", "info", None, None, "say what this is and what it will ask for",
           shared=(("trust", TRUST),)),
    Screen("handoff", "handoff", None, "patient_context",
           "a population the guided route does not carry yet — one honest line, then chat-first"),
    Screen("bill", "capture", "bill", "claim", "the bill being checked",
           shared=(("trust", TRUST),), example="itemized_bill", help_doc="itemized_bill",
           expect="itemized_bill", skippable=True),
    Screen("bill_itemized", "coach", "bill", "claim",
           "the bill is a summary — coach the itemized request, never proceed silently",
           shared=(("body", SUMMARY_COACHING),), example="summary_vs_itemized",
           help_doc="itemized_bill", expect="itemized_bill", skippable=True),
    Screen("bill_summary", "summary", "bill", "claim",
           "read the bill back, then ask ONCE about other bills for the same visit"),
    Screen("eob", "capture", "eob", "claim", "the insurer's statement for this visit",
           shared=(("trust", TRUST),), example="eob", help_doc="eob", expect="eob",
           skippable=True),
    Screen("card", "capture", "card", "plan_rules", "the insurance card",
           shared=(("trust", TRUST),), example="insurance_card", help_doc="insurance_card",
           expect="sbc", skippable=True),
    Screen("insurer", "fields", "card", "claim",
           "which insurer — asked ONLY when no document named it", skippable=True),
    Screen("coverage_type", "choice", "card", "patient_context",
           "which kind of coverage — asked only when detection could not tell"),
    Screen("plan_rules_confirm", "plan_confirm", "plan_rules", "plan_rules",
           "the Plan Library already has this plan — confirm it matches instead of uploading",
           variant_of="plan_rules"),
    Screen("plan_rules", "capture", "plan_rules", "plan_rules",
           "the Summary of Benefits and Coverage",
           shared=(("trust", TRUST),), example="sbc", help_doc="sbc", expect="sbc",
           skippable=True),
    Screen("plan_year", "choice", "timeline", "accumulators",
           "when the plan year starts — never assumed to be January 1",
           help_doc="plan_year", skippable=True),
    Screen("timeline", "timeline", "timeline", "accumulators",
           "every EOB since the plan year began, gaps named, completeness confirmed EVERY time",
           example="eob", help_doc="eob", expect="eob"),
    Screen("deductible_met", "fields", "timeline", "accumulators",
           "how much of the deductible was already paid — only when the EOBs cannot say",
           example="accumulators", help_doc="accumulators", skippable=True),
    Screen("oop_met", "fields", "timeline", "accumulators",
           "how much counted toward the out-of-pocket limit — only when the EOBs cannot say",
           example="accumulators", help_doc="accumulators", skippable=True),
    Screen("attest", "attest", "about_you", "patient_context",
           "the name on the bill is not the account holder — attest-and-proceed (existing machinery)"),
    Screen("other_insurance", "choice", "about_you", "patient_context",
           "a second plan — checked, never assumed to cover the rest", skippable=True),
    Screen("reading", "progress", "confirmations", "encounter_facts",
           "the engine is reading the bill — real stages only"),
    Screen("facts_only", "info", "confirmations", "encounter_facts",
           "the clinical boundary, as a screen: facts about the visit, never medical judgment"),
    Screen("confirmations", "confirmations", "confirmations", "encounter_facts",
           "one card per encounter fact the engine could not settle from paper"),
    Screen("readiness", "readiness", None, None,
           "the planner's own summary: resolved, unresolved, what each unresolved item limits"),
)
SCREENS: dict[str, Screen] = {s.id: s for s in SCREEN_REGISTRY}
SCREEN_IDS: tuple[str, ...] = tuple(SCREENS)


def next_screen(i: PlannerInputs, gaps: GapList | None = None) -> str:
    """The first registry screen that applies to this case — or READY (§A4-3)."""
    g = gaps or gap_list(i)
    if not g.on_guided_route:
        return "handoff"
    for screen in SCREEN_REGISTRY:
        if screen.id != "handoff" and _applies(screen.id, i, g):
            return screen.id
    return READY


def applicable(screen_id: str, i: PlannerInputs, gaps: GapList | None = None) -> bool:
    """May the user EDIT this screen now (the readiness links)? A satisfied ask is still
    editable; a screen the case has no use for (a manual deductible ask the EOBs already
    answered, an insurer ask the card settled) is not."""
    if screen_id not in SCREENS:
        return False
    g = gaps or gap_list(i)
    sc = SCREENS[screen_id]
    gap = next((x for x in g.gaps if x.screen == screen_id), None)
    if gap is not None:
        if gap.state == "not_needed":
            return False
        # the EOB stack answering an accumulator retires its manual screen entirely
        if screen_id in ("deductible_met", "oop_met") and i.accumulators_resolved:
            return False
        if screen_id == "insurer" and i.payer_known and gap.provenance == "document":
            return False
        return True
    return _applies(sc.id, i, g)


# ── progress (§A8) ───────────────────────────────────────────────────────────────────────
def groups_satisfied(i: PlannerInputs, g: GapList) -> list[str]:
    """Which of the seven segments have LANDED: nothing in the group is still unresolved and
    at least one thing in it was actually provided (a skip alone never fills a segment)."""
    s = g.state

    def done(*keys: str) -> bool:
        states = [s(k) for k in keys]
        return all(x in ("resolved", "not_needed", "skipped") for x in states) and any(
            x == "resolved" for x in states
        )

    out: list[str] = []
    if done("bill", "itemized_bill") and "bill_summary" in i.acked:
        out.append("bill")
    if i.card_present or (s("payer") == "resolved" and i.member_id_known):
        out.append("card")
    if done("plan_rules"):
        out.append("plan_rules")
    if done("eob"):
        out.append("eob")
    if done("plan_year_start", "eob_completeness", "deductible_met", "oop_max_met"):
        out.append("timeline")
    if done("coverage_type", "attestation", "other_insurance"):
        out.append("about_you")
    if done("encounter_facts"):
        out.append("confirmations")
    return out


def progress(i: PlannerInputs, g: GapList, high_water: Iterable[str] = ()) -> dict:
    """The segmented bar. It NEVER regresses: a segment that was ever filled stays filled
    (``high_water`` is persisted on the case), and if the live state no longer backs it —
    a document was reclassified — the bar keeps the segment and says why in one line."""
    live = groups_satisfied(i, g)
    kept = [x for x in high_water if x in PROGRESS_GROUPS]
    filled = [x for x in PROGRESS_GROUPS if x in live or x in kept]
    held = [x for x in filled if x not in live]  # filled by the high-water mark alone
    return {
        "segments": [{"group": x, "filled": x in filled} for x in PROGRESS_GROUPS],
        "filled": len(filled),
        "total": len(PROGRESS_GROUPS),
        "high_water": filled,
        "held": held,
    }


# ── readiness (#17) ──────────────────────────────────────────────────────────────────────
def readiness(i: PlannerInputs, g: GapList) -> dict:
    """The planner's own summary: every input it looked for, whether it has it, what an
    unresolved one LIMITS, and where to go to fix it."""
    lines = []
    for gap in g.gaps:
        if gap.state == "not_needed":
            continue
        editable = bool(gap.screen) and applicable(gap.screen, i, g)
        lines.append(
            {
                "key": gap.key,
                "group": gap.group,
                "resolved": gap.state == "resolved",
                "state": gap.state,
                "provenance": gap.provenance,
                "limits_key": None if gap.state == "resolved" else gap.limits,
                "edit_screen": gap.screen if editable else None,
            }
        )
    return {
        "lines": lines,
        "resolved": sum(1 for x in lines if x["resolved"]),
        "unresolved": sum(1 for x in lines if not x["resolved"]),
        # the audit can always run at the achievable rung — but never without a claim to check
        "can_run": i.bill_count > 0 or i.eob_count > 0,
    }
