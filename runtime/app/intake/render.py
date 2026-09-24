"""Planner decision → the wire descriptor the app draws.

The client holds NO intake copy and NO sequence: it renders ``screen.kind`` with the strings it
is given. Every string comes from the orchestration registry (verbatim, drift-guarded, graded);
a slot the registry cannot render honestly is omitted, never faked. An affordance appears only
when there is something behind it — "See an example" needs an asset, "Help me find it" needs a
document type, a skip needs its consequence line.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.agents.context_loader import load_orchestration_script, orchestration_step
from app.db.models.case_files import CaseFile
from app.ingestion.bill_heuristics import ITEMIZED_REQUEST_SCRIPT
from app.intake.examples import example_for
from app.intake.reading_level import terms_used
from app.intake.payer_instructions import BCBS_LOOKUP, BCBS_LOOKUP_PREFIX, HelpContext, instructions_for
from app.intake.planner import (
    CARD_TYPES,
    PROGRESS_GROUPS,
    READY,
    SCREENS,
    GapList,
    PlannerInputs,
    Screen,
    progress,
    readiness,
)
from app.intake.snapshot import COVERAGE_TYPE_OPTIONS, IntakeState
from app.intake.timeline import MONTH_NAMES, build_timeline

log = structlog.get_logger(__name__)

_FRIENDLY_DOC_TYPE = {
    "insurance_card": "an insurance card",
    "sbc": "a plan summary",
    "plan_summary": "a plan summary",
    "gfe": "a cost estimate",
    "clinical_record": "a medical record",
    "clinical_note": "a medical record",
    "medical_record": "a medical record",
}


def _renderable(text: str | None) -> str | None:
    if not text or text.startswith("<MISSING") or text.startswith("[PLACEHOLDER-eng]"):
        return None
    return text


def step(key: str, **variables: Any) -> str | None:
    """Render one registry key, or None. STRICT about variables: the thread's loader answers an
    unfilled ``{var}`` with its graceful-degradation line ("…that part is too blurry for me to
    trust…"), which is right in a thread and WRONG on an intake screen — the attest screen
    shipped showing it as its intro. A slot that cannot be rendered honestly is omitted."""
    raw = load_orchestration_script().get(key)
    if raw is None:
        return None
    given = {k: str(v) for k, v in variables.items() if v is not None and str(v) != ""}
    unfilled = {s.strip("{}") for s in _slots(raw)} - set(given)
    if unfilled:
        log.warning("intake.copy_variable_unfilled", key=key, unfilled=sorted(unfilled))
        return None
    return _renderable(orchestration_step(key, **given))


def group_copy(group: str, **variables: Any) -> dict[str, str]:
    """Every `intake.<group>.*` slot that needs no variable (or whose variables were given)."""
    prefix = f"intake.{group}."
    out: dict[str, str] = {}
    for key, raw in load_orchestration_script().items():
        if not key.startswith(prefix):
            continue
        slot = key[len(prefix) :]
        needs = {v.strip("{}") for v in _slots(raw)}
        if needs - set(variables):
            continue  # a variable this call cannot fill — that slot is rendered where it can be
        text = step(key, **{k: variables[k] for k in needs})
        if text:
            out[slot] = text
    return out


def _slots(raw: str) -> list[str]:
    import re

    return re.findall(r"\{[a-z_]+\}", raw or "")


def _population_label(population: str | None) -> str:
    return step(f"intake.handoff.label_{population or 'other'}") or step("intake.handoff.label_other") or ""


def _screen_variables(screen: Screen, i: PlannerInputs, data: dict) -> dict[str, Any]:
    v: dict[str, Any] = {}
    if screen.id == "handoff":
        v["population_label"] = _population_label(i.population)
    if screen.id == "plan_rules_confirm":
        v["payer"] = (i.coverage or {}).get("payer_name") or "your insurer"
    if screen.id == "bill_itemized":
        v["itemized_request_script"] = ITEMIZED_REQUEST_SCRIPT
    return v


def _timeline_copy(tl: dict) -> dict[str, str]:
    """The completeness confirmation (locked 5d) — the variant that matches what was counted."""
    n, start, end = tl["count"], tl["span_start"], tl["span_end"]
    out: dict[str, str] = {}
    if n <= 0:
        return out
    if tl["covers_family"]:
        text = step("intake.timeline.confirm_family", n=n, start=start or "", end=end or "",
                    members=len(tl["members"]))
    elif n == 1 or not start or start == end:
        text = step("intake.timeline.confirm_one", start=start or "this year")
    else:
        text = step("intake.timeline.confirm", n=n, start=start, end=end)
    if text:
        out["confirm_text"] = text
    gaps = [g for g in (step("intake.timeline.gap", month=x["label"]) for x in tl["gaps"]) if g]
    if gaps:
        out["gap_lines"] = "\n".join(gaps)
    return out


def _data_for(screen: Screen, case: CaseFile, i: PlannerInputs, g: GapList, proposal: Any) -> dict:
    sid = screen.id
    if screen.kind == "capture" or sid == "bill_itemized":
        note = None
        if sid in ("bill", "eob") and i.wrong_document:
            types = [d.get("document_type") for d in (case.documents or []) if isinstance(d, dict)]
            friendly = next((_FRIENDLY_DOC_TYPE[t] for t in types if t in _FRIENDLY_DOC_TYPE), "something else")
            note = step(f"wrongdoc.{i.wrong_document}", detected_doc_type=friendly)  # §C12 — existing §5.3
        have = {"bill": i.bill_count, "bill_itemized": i.bill_count, "eob": i.eob_count,
                "card": int(i.card_present), "plan_rules": int(i.sbc_on_file)}.get(sid, 0)
        return {"expect": screen.expect, "have": have, "note": note}
    if sid == "bill_summary":
        return {
            "rows": [
                {"slot": "row_provider", "value": i.provider},
                {"slot": "row_date", "value": i.date_of_service.isoformat() if i.date_of_service else None},
                {"slot": "row_patient", "value": i.patient_name},
                {"slot": "row_account", "value": case.account_number},
            ],
            "bill_count": i.bill_count,
        }
    if sid == "coverage_type":
        return {"options": [{"value": k, "slot": f"opt_{k}"} for k in COVERAGE_TYPE_OPTIONS]}
    if sid == "plan_year":
        return {"options": [{"value": str(m), "label": MONTH_NAMES[m - 1]} for m in range(1, 13)]
                + [{"value": "not_sure", "slot": "opt_not_sure"}]}
    if sid == "other_insurance":
        return {"options": [{"value": v, "slot": v} for v in ("yes", "no", "not_sure")]}
    if sid == "insurer":
        cov = i.coverage or {}
        # a LOW-confidence card read is offered for the user to confirm or fix — never merged
        # silently, never discarded (routes/intake._read_new_cards)
        weak = IntakeState(case).get("card_reads") or {}

        def _field(name: str, slot: str) -> dict:
            known = cov.get(name)
            return {"name": name, "slot": slot, "value": known or weak.get(name), "input": "text",
                    "suggested": bool(not known and weak.get(name)),
                    # the answer route needs the insurer's name; the member ID is "if you have it"
                    "required": name == "payer_name"}

        return {"fields": [_field("payer_name", "field_payer"), _field("member_id", "field_member_id")]}
    if sid == "blue_plan":
        # the BCBS router's question (portal guide). The member ID, when a document gave it, already
        # carries the three letters — offered, never silent
        member = str((i.coverage or {}).get("member_id") or "")[:3]
        prefix = member.upper() if len(member) == 3 and member.isalnum() and not member.isdigit() else None
        return {"fields": [
            {"name": "plan_name", "slot": "field_plan_name", "value": None, "input": "text", "required": True},
            {"name": "id_prefix", "slot": "field_id_prefix", "value": prefix, "input": "text",
             "suggested": bool(prefix), "required": False},
        ]}
    if sid in ("deductible_met", "oop_met"):
        name = "deductible_met" if sid == "deductible_met" else "oop_max_met"
        return {"fields": [{"name": name, "slot": "field_amount", "value": (i.coverage or {}).get(name),
                            "input": "usd"}]}
    if sid == "plan_rules_confirm" and proposal is not None:
        design = dict(getattr(proposal, "benefit_design", None) or {})
        return {"plan_library_id": proposal.plan_library_id, "payer": proposal.payer,
                "plan_name": proposal.plan_name, "plan_year": proposal.plan_year,
                "rows": [
                    {"slot": "row_deductible", "value": design.get("deductible_amount"), "unit": "usd"},
                    {"slot": "row_oop", "value": design.get("oop_max_amount"), "unit": "usd"},
                    {"slot": "row_coinsurance", "value": design.get("coinsurance_percent"), "unit": "fraction"},
                ]}
    if sid == "timeline":
        return build_timeline(case, plan_year_start=i.plan_year_start, date_of_service=i.date_of_service)
    if sid == "attest":
        # The relationship menu, the confirm line and the decline path are the EXISTING attest
        # machinery (agents/attest.py + routes/attest.py); this screen only hosts them.
        from app.agents.attest import RELATIONSHIPS, attest_edge_signals

        # Every attest key is rendered with the variables the existing machinery defines
        # (agents.attest.attest_variables) — several carry {patient_name}.
        from app.agents.attest import attest_variables
        from app.sources.extraction import plausible_extracted_name

        v = attest_variables(case, first_name=i.account_first_name)
        return {
            "declined": i.attest_status == "declined",
            "patient_name": i.patient_name if plausible_extracted_name(i.patient_name) else None,
            "intro": step("attest.intro", **v),
            "confirm": step("attest.confirm", **v),
            "decline_ack": step("attest.decline_ack", **v),
            "relationships": [{"value": r, "label": step(f"attest.menu_{r}", **v)} for r in RELATIONSHIPS],
            "edge_prompts": [t for s in attest_edge_signals(case) if (t := step(f"attest.edge_{s}", **v))],
        }
    if sid == "confirmations":
        # ONE card per fact the engine emitted and nobody has answered yet — never capped, never
        # padded (§A4-5), never a fact asked twice (R1: the registry every surface reads). Each
        # card says the code and ONE plain sentence under the grade-5 guard; the rest goes under
        # the disclosure (R4 — the chat-first cap, which never reached this screen).
        from app.agents.encounter_facts import registry
        from app.intake.fact_copy import fact_card

        fallback = step("intake.confirmations.fact_fallback")
        return {"line_items": [
            {"line_item_id": li.get("line_item_id"),
             "fact_id": li["fact_id"],
             "code": li.get("code") or None,
             **fact_card(li, fallback)}
            for li in registry(case).pending if li.get("line_item_id")
        ]}
    if sid == "readiness":
        r = readiness(i, g)
        for line in r["lines"]:
            line["label"] = step(f"intake.readiness.item_{line['key']}")
            line["limits"] = step(line["limits_key"]) if line["limits_key"] else None
        return r
    return {}


def render_screen(
    screen_id: str, case: CaseFile, i: PlannerInputs, g: GapList, *, proposal: Any = None
) -> dict:
    if screen_id == READY:
        return {"id": READY, "kind": "ready", "progress_group": None, "copy": group_copy("analysis"),
                "data": {}, "skippable": False}
    screen = SCREENS[screen_id]
    data = _data_for(screen, case, i, g, proposal)
    variables = _screen_variables(screen, i, data)
    copy = group_copy(screen.id, **variables)
    for slot, key in screen.shared:
        text = step(key, **{k: variables[k] for k in (s.strip("{}") for s in _slots(load_orchestration_script().get(key, ""))) if k in variables})
        if text:
            copy[slot] = text
    if screen.id == "timeline":
        copy.update(_timeline_copy(data))
    if screen.id == "insurer":
        # "I could not find it" would be untrue beside a field I pre-filled from the card
        read_it = copy.pop("body_suggested", None)
        if read_it and any(f.get("suggested") for f in data.get("fields", [])):
            copy["body"] = read_it

    out: dict[str, Any] = {
        "id": screen.id,
        "kind": screen.kind,
        "progress_group": screen.progress_group,
        "copy": copy,
        "data": data,
        "skippable": screen.skippable,
    }
    ex = example_for(screen.example)
    if ex is not None:  # nothing to show → no affordance (never an empty sheet)
        title = step(ex.title_key) if ex.title_key else None
        # doc 41: the drawn illustration + Brock's legend when its image is bundled; otherwise the
        # federal sample (SBC, MSN) with its "look for this" callouts, as before. A sample's
        # callouts + source line ride along even once it is illustrated: the APP picks by what its
        # build bundles, so a tab still running last week's bundle falls back to them, whole
        legend = [t for k in ex.legend_keys if (t := step(k))] if ex.illustrated else []
        callouts = [t for k in ex.callout_keys if (t := step(k))]
        # only the glosses this sheet's own words need (e2e round 3 R6: the SBC sample carried
        # the MSN gloss — every example gloss rode on every sheet)
        used = terms_used(" ".join([title or "", *legend, *callouts]))
        out["example"] = {
            "ask": ex.ask,
            "title": title,
            "illustration": {"slot": ex.illustration, "aspect": ex.aspect} if ex.illustrated else None,
            "legend": legend,
            "callouts": callouts,
            "asset": (
                {"kind": ex.asset.kind, "url": ex.asset.url, "publisher": ex.asset.publisher}
                if ex.asset is not None else None
            ),
            "source_line": step("intake.example.source_federal") if ex.asset else None,
            "glosses": {
                term: v for k, v in group_copy("example").items()
                if k.startswith("gloss_") and (term := k[len("gloss_"):]) in used
            },
        }
    if screen.help_doc:
        ctx = help_context(case, payer_name=(i.coverage or {}).get("payer_name"))
        help_ = render_help(ctx, screen.help_doc, screen.id)
        if help_:
            out["help"] = help_
    return out


def help_context(case: CaseFile, *, payer_name: str | None = None) -> HelpContext:
    """What "Help me find it" may know about this case: the payer (the planner passes the
    EFFECTIVE coverage's name), the BCBS router's answer, and whether the card is on file or the
    user said they don't have it."""
    st = IntakeState(case)
    blue = st.answers.get("blue_plan") or {}
    types = {d.get("document_type") for d in (case.documents or []) if isinstance(d, dict)}
    return HelpContext(
        payer_name=payer_name or (case.coverage or {}).get("payer_name"),
        blue_plan_name=blue.get("plan_name"),
        id_prefix=blue.get("id_prefix"),
        card_on_file=bool(types & CARD_TYPES),
        card_skipped="card" in st.skipped,
    )


def render_help(
    ctx: HelpContext | None, document_type: str, screen_id: str | None = None, *, for_email: bool = False
) -> dict | None:
    """The "Where to find it" sheet. ``for_email`` drops the one line that carries something
    read from the user's card (the member-ID prefix on the bcbs.com lookup): the email is generic
    steps + the payer's name, nothing else (DL-47)."""
    ctx = ctx or HelpContext()
    found = instructions_for(document_type, screen_id, ctx)
    if found is None:
        return None

    def _line(key: str) -> str | None:
        if key == BCBS_LOOKUP and ctx.id_prefix and not for_email:
            return step(BCBS_LOOKUP_PREFIX, prefix=ctx.id_prefix) or step(key)
        return step(key)

    steps = [*found["steps"], *(t for k in found["step_keys"] if (t := _line(k)))]
    if not steps:
        return None
    note = (
        step("intake.help.payer_note", payer=found["payer_name"])
        if found["scope"] == "payer"
        else step("intake.help.generic_note")
    )
    return {
        "document_type": document_type,
        "scope": found["scope"],
        "payer_name": found["payer_name"],
        "title": step("intake.help.title"),
        "note": note,
        "steps": steps,
        "verified": found["verified"],
        "can_email": True,  # the one existing send path; SMS is not built and is not offered
    }


def render_progress(i: PlannerInputs, g: GapList, high_water: list[str]) -> dict:
    p = progress(i, g, high_water)
    labels = group_copy("progress")
    filled, total = p["filled"], p["total"]
    if filled <= 0:
        line = None  # nothing has landed — no counter, and never a bare "Step N of M"
    elif filled >= total:
        line = step("intake.progress.all", total=total)
    elif filled == 1:
        line = step("intake.progress.started", filled=filled, total=total)  # "1 of 7 — nice start"
    else:
        line = step("intake.progress.going", filled=filled, total=total)
    return {
        "segments": [
            {"group": s["group"], "filled": s["filled"], "label": labels.get(f"label_{s['group']}")}
            for s in p["segments"]
        ],
        "filled": filled,
        "total": total,
        "line": line,
        # a segment held by the high-water mark alone: the document behind it was reclassified
        "note": labels.get("kept_note") if p["held"] else None,
        "glosses": {"eob": labels.get("gloss_eob")},
        "high_water": p["high_water"],
    }


assert set(PROGRESS_GROUPS) == {
    "bill", "card", "plan_rules", "eob", "timeline", "about_you", "confirmations",
}  # fmt: skip
