"""Planner decision → the wire descriptor the app draws.

The client holds NO intake copy and NO sequence: it renders ``screen.kind`` with the strings it
is given. Every string comes from the orchestration registry (verbatim, drift-guarded, graded);
a slot the registry cannot render honestly is omitted, never faked. An affordance appears only
when there is something behind it — "See an example" needs an asset, "Help me find it" needs a
document type, a skip needs its consequence line.
"""

from __future__ import annotations

from typing import Any

from app.agents.context_loader import load_orchestration_script, orchestration_step
from app.db.models.case_files import CaseFile
from app.ingestion.bill_heuristics import ITEMIZED_REQUEST_SCRIPT
from app.intake.examples import example_for
from app.intake.payer_instructions import instructions_for
from app.intake.planner import (
    PROGRESS_GROUPS,
    READY,
    SCREENS,
    GapList,
    PlannerInputs,
    Screen,
    progress,
    readiness,
)
from app.intake.snapshot import COVERAGE_TYPE_OPTIONS
from app.intake.timeline import MONTH_NAMES, build_timeline

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
    return _renderable(orchestration_step(key, **{k: str(v) for k, v in variables.items()}))


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
        return {"fields": [
            {"name": "payer_name", "slot": "field_payer", "value": cov.get("payer_name"), "input": "text"},
            {"name": "member_id", "slot": "field_member_id", "value": cov.get("member_id"), "input": "text"},
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

        return {
            "declined": i.attest_status == "declined",
            "patient_name": i.patient_name,
            "intro": step("attest.intro", patient_name=i.patient_name or "someone else"),
            "confirm": step("attest.confirm"),
            "decline_ack": step("attest.decline_ack"),
            "relationships": [{"value": r, "label": step(f"attest.menu_{r}")} for r in RELATIONSHIPS],
            "edge_prompts": [t for s in attest_edge_signals(case) if (t := step(f"attest.edge_{s}"))],
        }
    if sid == "confirmations":
        # ONE card per fact the engine emitted — never capped, never padded (§A4-5).
        return {"line_items": [
            {"line_item_id": li.get("line_item_id"),
             "text": li.get("plain_language_translation") or li.get("raw_description"),
             "context": li.get("plain_language_context") or None}
            for li in (case.line_items or []) if isinstance(li, dict) and li.get("line_item_id")
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

    out: dict[str, Any] = {
        "id": screen.id,
        "kind": screen.kind,
        "progress_group": screen.progress_group,
        "copy": copy,
        "data": data,
        "skippable": screen.skippable,
    }
    ex = example_for(screen.example)
    if ex is not None:  # no asset → no affordance (never an empty sheet)
        out["example"] = {
            "ask": ex.ask,
            "title": step(ex.title_key) if ex.title_key else None,
            "callouts": [t for k in ex.callout_keys if (t := step(k))],
            "asset": {"kind": ex.asset.kind, "url": ex.asset.url, "publisher": ex.asset.publisher},
            "source_line": step("intake.example.source_federal"),
            "glosses": {k[len("gloss_"):]: v for k, v in group_copy("example").items() if k.startswith("gloss_")},
        }
    if screen.help_doc:
        help_ = render_help((i.coverage or {}).get("payer_name"), screen.help_doc, screen.id)
        if help_:
            out["help"] = help_
    return out


def render_help(payer_name: str | None, document_type: str, screen_id: str | None = None) -> dict | None:
    found = instructions_for(payer_name, document_type, screen_id)
    if found is None:
        return None
    steps = found["steps"] or [t for k in found["step_keys"] if (t := step(k))]
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
