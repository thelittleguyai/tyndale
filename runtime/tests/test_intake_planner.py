"""The Intake Planner (doc 40 §A4) — a planner, not a wizard. Pure tests: a snapshot in, a
screen out. Every rule the packet states is one test; none touches the database."""

from __future__ import annotations

import dataclasses
import datetime

import pytest

from app.intake import planner as ip
from app.intake.planner import READY, PlannerInputs, gap_list, next_screen, progress, readiness

# A commercial case with everything in: the planner has nothing left to ask.
DONE = PlannerInputs(
    bill_count=1,
    eob_count=3,
    card_present=True,
    payer_known=True,
    member_id_known=True,
    sbc_on_file=True,
    missing_cost_share=(),
    population="commercial",
    regime="erisa_self_funded",
    plan_year_start="2026-01-01",
    plan_year_source="sbc",
    completeness_confirmed=True,
    secondary_answered=True,
    line_items=4,
    confirmations_done=True,
    case_status="encounter_verified",
    coverage={"deductible_amount": 2000.0, "oop_max_amount": 6000.0, "coinsurance_percent": 0.2,
              "payer_name": "Aetna", "member_id": "W1"},
    acked=frozenset({"welcome", "bill_summary", "facts_only", "readiness"}),
)


def _with(**over) -> PlannerInputs:
    return dataclasses.replace(DONE, **over)


def _walk(i: PlannerInputs) -> list[str]:
    """Every screen the planner would raise for this snapshot if the user only ever ACKED or
    SKIPPED — i.e. the set of things it thinks are still worth asking."""
    seen: list[str] = []
    for _ in range(40):
        s = next_screen(i)
        if s in (READY, "handoff") or s in seen:
            seen.append(s)
            break
        seen.append(s)
        i = dataclasses.replace(i, acked=i.acked | {s}, skipped=i.skipped | {s})
    return seen


def test_a_complete_case_is_ready_and_an_empty_one_starts_at_the_welcome():
    assert next_screen(DONE) == READY
    assert next_screen(PlannerInputs()) == "welcome"
    assert next_screen(PlannerInputs(acked=frozenset({"welcome"}))) == "bill"


# ── skip-when-known (§A4-3) ──────────────────────────────────────────────────────────────
def test_a_card_that_named_the_payer_means_no_which_insurer_screen():
    named = _with(acked=frozenset({"welcome", "bill_summary"}), sbc_on_file=True)
    assert "insurer" not in _walk(named)
    # …and it IS asked when a card was read but carried no payer
    unnamed = _with(payer_known=False, member_id_known=False, coverage={}, sbc_on_file=True)
    assert next_screen(unnamed) == "insurer"
    # "it's already on your bill" (§B7): payer + member id from the bill → the card is not asked for
    from_bill = _with(card_present=False)
    assert "card" not in _walk(from_bill)


def test_i_dont_have_my_card_leads_to_typing_the_insurer_not_to_silence():
    """§B7: "I don't have my card" → type insurer + member ID, or it's already on your bill/EOB.
    Skipping the card used to mark the payer gap skipped, so the typed ask never appeared."""
    no_card = _with(card_present=False, payer_known=False, member_id_known=False, skipped=frozenset({"card"}))
    assert "insurer" in _walk(no_card)
    # already on the bill/EOB → nothing to type
    on_the_bill = _with(card_present=False, payer_known=True, member_id_known=True, skipped=frozenset({"card"}))
    assert "insurer" not in _walk(on_the_bill)
    # and skipping the typed ask too is an honest "unknown", surfaced at readiness
    both = _with(card_present=False, payer_known=False, skipped=frozenset({"card", "insurer"}))
    assert "insurer" not in _walk(both)


def test_an_eob_stack_that_resolves_the_accumulators_retires_the_manual_screens():
    resolved = _with(completeness_confirmed=True, eobs_undated=0)
    assert resolved.accumulators_resolved
    walked = _walk(resolved)
    assert "deductible_met" not in walked and "oop_met" not in walked
    assert not ip.applicable("deductible_met", resolved)  # not even reachable from readiness

    # the user says the stack is NOT complete → the engine cannot rebuild the position → ask
    partial = _with(completeness_confirmed=False)
    assert next_screen(partial) == "deductible_met"
    # an undated EOB cannot be placed in the year either
    undated = _with(eobs_undated=1)
    assert next_screen(undated) == "deductible_met"
    # …unless the user already told us, or said "not sure" (both are answers)
    assert next_screen(_with(completeness_confirmed=False, deductible_met_known=True, oop_met_known=True)) == READY


def test_a_plan_library_match_shows_confirm_this_matches_instead_of_upload():
    no_rules = dict(sbc_on_file=False, coverage={"payer_name": "Aetna", "member_id": "W1"},
                    missing_cost_share=("deductible_amount", "oop_max_amount", "coinsurance_percent"))
    assert next_screen(_with(**no_rules, plan_proposal=True)) == "plan_rules_confirm"
    assert next_screen(_with(**no_rules, plan_proposal=False)) == "plan_rules"
    # an SBC on file — even one whose extraction read nothing — is never asked for again
    assert "plan_rules" not in _walk(_with(**{**no_rules, "sbc_on_file": True}))


def test_a_summary_bill_gets_the_coaching_screen_and_is_never_waved_through():
    summary = _with(bill_is_summary=True, acked=frozenset({"welcome"}))
    assert next_screen(summary) == "bill_itemized"
    # coached ONCE: "keep going with this bill" is honoured, and readiness says what it costs
    kept = _with(bill_is_summary=True, skipped=frozenset({"bill_itemized"}),
                 acked=DONE.acked | {"bill_itemized"})
    assert next_screen(kept) == READY
    line = next(x for x in readiness(kept, gap_list(kept))["lines"] if x["key"] == "itemized_bill")
    assert line["state"] == "skipped" and line["limits_key"] == "intake.limits.summary_bill"


def test_a_name_that_is_not_the_account_holder_becomes_attest_and_proceed():
    assert next_screen(_with(attest_status="required")) == "attest"
    assert "attest" not in _walk(_with(attest_status="not_required"))
    assert "attest" not in _walk(_with(attest_status="attested"))


def test_other_bills_for_this_visit_is_asked_once_right_after_the_read_back():
    fresh = PlannerInputs(bill_count=1, acked=frozenset({"welcome"}))
    assert next_screen(fresh) == "bill_summary"
    # a second bill attached to the SAME case does not re-ask once it was answered
    again = dataclasses.replace(fresh, bill_count=2, acked=frozenset({"welcome", "bill_summary"}))
    assert next_screen(again) != "bill_summary"


def test_i_dont_have_the_bill_starts_with_the_eob_instead():
    no_bill = PlannerInputs(acked=frozenset({"welcome"}), skipped=frozenset({"bill"}))
    assert next_screen(no_bill) == "eob"


# ── coverage population: commercial only in Phase 1 (§A4-4) ──────────────────────────────
@pytest.mark.parametrize(
    ("regime", "population"),
    [("medicare_traditional", "medicare"), ("medicare_advantage", "medicare_advantage"),
     ("medicaid_mco", "medicaid"), ("dual_eligible", "dual"), ("self_pay", "self_pay"),
     ("tricare", "tricare_va"), ("va_champva", "tricare_va"), ("stldi", "other")],
)
def test_every_non_commercial_population_exits_to_chat_first(regime, population):
    assert ip.population_of(regime) == population
    i = _with(regime=regime, population=population)
    assert next_screen(i) == "handoff"  # from ANY point — the very next state after detection
    assert next_screen(PlannerInputs(population=population)) == "handoff"


@pytest.mark.parametrize("regime", ["state_regulated_commercial", "erisa_self_funded", "fehb_pshb", "nonfederal_governmental"])
def test_commercial_shaped_plans_ride_the_guided_route(regime):
    assert ip.population_of(regime) == "commercial"
    assert next_screen(_with(regime=regime)) == READY


def test_an_unknown_population_is_asked_never_guessed():
    unknown = _with(population=None, regime=None)
    assert unknown.on_guided_route
    assert next_screen(unknown) == "coverage_type"


# ── confirmations are generated, not fixed (§A4-5) ───────────────────────────────────────
@pytest.mark.parametrize("n", [0, 1, 5])
def test_the_confirmation_count_is_whatever_the_engine_emitted(n):
    i = _with(line_items=n, confirmations_done=False, case_status="encounter_verification_pending",
              acked=DONE.acked - {"facts_only"})
    gap = gap_list(i).get("encounter_facts")
    if n == 0:
        assert gap.state == "not_needed"  # never padded: nothing to confirm → no screen at all
        assert next_screen(i) == READY
    else:
        assert gap.state == "unresolved"
        assert next_screen(i) == "facts_only"  # the clinical boundary first…
        assert next_screen(dataclasses.replace(i, acked=i.acked | {"facts_only"})) == "confirmations"


def test_while_the_engine_is_still_reading_the_user_waits_on_a_real_stage():
    reading = _with(line_items=0, confirmations_done=False, case_status="open")
    assert next_screen(reading) == "reading"


# ── the completeness confirmation is asked EVERY time (locked 5d) ────────────────────────
def test_completeness_is_asked_whenever_there_is_a_stack_to_count():
    assert next_screen(_with(completeness_confirmed=None)) == "timeline"
    assert gap_list(_with(eob_count=0, completeness_confirmed=None)).state("eob_completeness") == "not_needed"
    # "no, there are more" IS an answer — it is not re-asked, it downgrades the accumulators
    assert next_screen(_with(completeness_confirmed=False, deductible_met_known=True, oop_met_known=True)) == READY


def test_the_plan_year_start_is_never_assumed():
    assert next_screen(_with(plan_year_start=None, plan_year_source=None)) == "plan_year"
    assert "plan_year" not in _walk(_with(plan_year_start="2025-07-01", plan_year_source="sbc"))


# ── silent vs ask: the EXISTING materiality ladder (§A4, last paragraph) ─────────────────
def test_load_bearing_is_the_user_chase_bar_over_the_priors():
    from app.sources.materiality import USER_CHASE, is_material
    from app.sources.missing_data_priors import MISSING_DATA_PRIORS

    for key in ("deductible_amount", "oop_max_amount", "coinsurance_percent", "copay_pcp"):
        p = MISSING_DATA_PRIORS[key]
        assert ip.load_bearing(key) == is_material(p.usd_span(), p.high, USER_CHASE)
    assert ip.load_bearing("deductible_amount") and not ip.load_bearing("coinsurance_percent")
    # an accumulator can swing the answer by at most its cap: a $0-deductible plan never asks
    assert not ip.load_bearing("deductible_met", {"deductible_amount": 0})
    assert ip.load_bearing("deductible_met", {"deductible_amount": 2500})
    zero = _with(completeness_confirmed=False, coverage={**DONE.coverage, "deductible_amount": 0, "oop_max_amount": 0})
    assert gap_list(zero).state("deductible_met") == "not_needed"
    assert next_screen(zero) == READY


# ── progress never regresses (§A8) ───────────────────────────────────────────────────────
def test_progress_frames_the_first_landing_as_a_start_and_never_goes_backwards():
    one = PlannerInputs(bill_count=1, acked=frozenset({"welcome", "bill_summary"}))
    p1 = progress(one, gap_list(one))
    assert (p1["filled"], p1["total"]) == (1, 7) and p1["high_water"] == ["bill"]

    # the "bill" is RECLASSIFIED as something else: the live state no longer backs the segment
    reclassified = dataclasses.replace(one, bill_count=0)
    live = progress(reclassified, gap_list(reclassified))
    assert live["filled"] == 0  # without the mark, the bar WOULD drop…
    kept = progress(reclassified, gap_list(reclassified), high_water=p1["high_water"])
    assert kept["filled"] == 1 and kept["held"] == ["bill"]  # …with it, it does not, and says why
    assert [s["filled"] for s in kept["segments"]][0] is True


def test_a_skip_alone_never_fills_a_segment():
    skipped = PlannerInputs(acked=frozenset({"welcome"}), skipped=frozenset({"eob"}))
    assert "eob" not in progress(skipped, gap_list(skipped))["high_water"]


def test_the_seven_segments_are_the_packets_seven_in_order():
    assert ip.PROGRESS_GROUPS == ("bill", "card", "plan_rules", "eob", "timeline", "about_you", "confirmations")
    assert {s.progress_group for s in ip.SCREEN_REGISTRY if s.progress_group} == set(ip.PROGRESS_GROUPS)


# ── readiness is the planner's own summary (#17) ─────────────────────────────────────────
def test_readiness_lists_what_is_missing_what_it_limits_and_where_to_fix_it():
    thin = PlannerInputs(bill_count=1, population="commercial",
                         acked=frozenset({"welcome", "bill_summary"}),
                         skipped=frozenset({"eob", "card", "insurer", "plan_rules", "plan_year", "other_insurance"}),
                         missing_cost_share=("deductible_amount", "oop_max_amount", "coinsurance_percent"),
                         case_status="encounter_verification_pending")
    r = readiness(thin, gap_list(thin))
    by = {x["key"]: x for x in r["lines"]}
    assert by["bill"]["resolved"] and by["bill"]["limits_key"] is None
    assert by["eob"]["state"] == "skipped" and by["eob"]["limits_key"] == "intake.limits.no_eob"
    assert by["eob"]["edit_screen"] == "eob"  # an edit link on every line that can be edited
    assert by["plan_rules"]["limits_key"] == "intake.limits.no_plan_rules"
    assert r["can_run"] and r["unresolved"] >= 4
    assert not readiness(PlannerInputs(), gap_list(PlannerInputs()))["can_run"]  # nothing to check


def test_the_five_input_groups_are_all_represented():
    assert {g.group for g in gap_list(PlannerInputs()).gaps} == set(ip.INPUT_GROUPS)


# ── the registry is data, and the analytics enum follows it ──────────────────────────────
def test_every_screen_has_copy_in_the_script_and_every_intake_key_has_a_home():
    from app.agents.context_loader import load_orchestration_script

    keys = [k for k in load_orchestration_script() if k.startswith("intake.")]
    groups = {k.split(".")[1] for k in keys}
    assert groups <= set(ip.SCREEN_IDS) | set(ip.SUPPORT_GROUPS), groups - set(ip.SCREEN_IDS) - set(ip.SUPPORT_GROUPS)
    for s in ip.SCREEN_REGISTRY:
        assert f"intake.{s.id}.title" in keys, f"{s.id} has no title in the orchestration script"
    for g in gap_list(PlannerInputs()).gaps:
        assert f"intake.readiness.item_{g.key}" in keys, g.key
        assert g.limits is None or g.limits in keys, g.limits
        assert g.screen in ip.SCREENS


def test_the_funnel_events_accept_every_screen_and_population():
    from app.analytics.events import _INTAKE_POPULATIONS, _INTAKE_SCREENS

    assert set(_INTAKE_SCREENS) == set(ip.SCREEN_IDS) | {"ready"}
    assert set(_INTAKE_POPULATIONS) == set(ip.POPULATIONS)


def test_plan_year_start_follows_the_visit_not_the_calendar():
    from app.intake.timeline import plan_year_start_for

    assert plan_year_start_for(7, datetime.date(2026, 6, 14)) == "2025-07-01"  # July plan, June visit
    assert plan_year_start_for(7, datetime.date(2026, 8, 2)) == "2026-07-01"
    assert plan_year_start_for(1, datetime.date(2026, 6, 14)) == "2026-01-01"


# ── a way out always says what it costs ──────────────────────────────────────────────────
WAY_OUT_SLOTS = {"skip": "skip_consequence", "no_bill": "no_bill_note", "secondary": "secondary_consequence",
                 "not_sure": "not_sure_consequence", "opt_not_sure": "not_sure_consequence"}


def test_every_way_out_of_a_screen_carries_its_consequence_line():
    """Skips are honest (§A4, §B): any screen that offers "skip" / "I don't have it" / "I'm not
    sure" ALSO carries the line that says what that costs the audit. Found by walking the flow —
    `insurer`, `plan_year` and `other_insurance` shipped a way out with nothing beside it."""
    from app.agents.context_loader import load_orchestration_script

    script = load_orchestration_script()
    missing = []
    for sc in ip.SCREEN_REGISTRY:
        slots = {k.split(".", 2)[2] for k in script if k.startswith(f"intake.{sc.id}.")}
        for way_out, consequence in WAY_OUT_SLOTS.items():
            if way_out in slots and consequence not in slots and not (
                sc.id == "confirmations" and "not_sure_note" in slots  # §B16: its own reassurance line
            ):
                missing.append(f"intake.{sc.id}.{way_out} has no intake.{sc.id}.{consequence}")
    assert not missing, missing
    # and the inverse: a skippable screen really does offer a way out
    for sc in ip.SCREEN_REGISTRY:
        if sc.skippable:
            slots = {k.split(".", 2)[2] for k in script if k.startswith(f"intake.{sc.id}.")}
            assert slots & set(WAY_OUT_SLOTS), f"{sc.id} is skippable but offers no way out"

