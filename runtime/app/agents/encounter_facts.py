"""Encounter facts — one registry, one identity (e2e round 3, R1).

Every charge the translate pass emits is an ENCOUNTER FACT the user confirms ("yes / that didn't
happen / not sure"). Round 3 found the same three charges asked twice on the guided case and a
completed case pulled back into verification: a second translate run appended freshly worded
copies of every line item with freshly minted ``line_item_id``s, the confirmations were keyed by
the OLD ids, so nothing could tell that the new cards were facts the user had already answered.

The identity is now derived from what the charge IS, never from how it was worded or which run
minted it:

    fact_id = uuid5(case_file_id, "enc-v1|<CODE>|<DOS>|<k>")

  CODE  the billing code, upper-cased, modifiers joined by "-"  ("99214 25" → "99214-25")
  DOS   the line's own date of service when the line carries one, else the case's date of
        service, else ""  (ISO yyyy-mm-dd)
  k     1-based occurrence of (CODE, DOS) in the bill's line order — two identical charges on
        the same day are two facts, and a duplicate charge is exactly what the audit looks for

``line_item_id`` stays the per-row handle the clients post answers with; it is NOT part of the
identity (the translate tool mints a fresh uuid4 per call, so it cannot survive a re-run).
A persisted ``fact_id`` is never recomputed — a case whose date of service became known after
its first read keeps the ids its answers were recorded against.

Every reader builds its card list from ``registry(case)``: the intake planner's confirmations
screen, the thread bridge's verification cards, the free-text mapper, and the orchestrator's
extract / confirm steps. A fact with a recorded answer is never asked again. Wording is
presentation, never identity.
"""

from __future__ import annotations

import datetime
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

FACT_ID_SCHEME = "enc-v1"
_CODE_JOIN = re.compile(r"[^A-Z0-9]+")


def normalize_code(code: Any) -> str:
    return _CODE_JOIN.sub("-", str(code or "").upper()).strip("-")


def _iso_date(value: Any) -> str:
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        return ""


def service_date(item: dict, case_dos: Any = None) -> str:
    return _iso_date(item.get("date_of_service")) or _iso_date(case_dos)


def fact_id_for(case_file_id: str, code: str, dos: str, k: int) -> str:
    return str(uuid.uuid5(uuid.UUID(str(case_file_id)), f"{FACT_ID_SCHEME}|{code}|{dos}|{k}"))


def stamp(items: list, case_file_id: str, case_dos: Any = None) -> list[dict]:
    """Copies of ``items`` (dicts only), each carrying its ``fact_id``. Deterministic: the same
    charges in the same order always get the same ids, however they are worded."""
    out = [dict(it) for it in (items or []) if isinstance(it, dict)]
    used = {it["fact_id"] for it in out if it.get("fact_id")}
    seen: Counter = Counter()
    for it in out:
        key = (normalize_code(it.get("code")), service_date(it, case_dos))
        seen[key] += 1
        if it.get("fact_id"):
            continue
        k = seen[key]
        fid = fact_id_for(case_file_id, *key, k)
        while fid in used:  # a persisted id already holds this slot — take the next occurrence
            k += 1
            fid = fact_id_for(case_file_id, *key, k)
        it["fact_id"] = fid
        used.add(fid)
    return out


@dataclass(frozen=True)
class FactRegistry:
    facts: list[dict]
    answers: dict[str, dict] = field(default_factory=dict)  # fact_id → the recorded confirmation

    @property
    def pending(self) -> list[dict]:
        return [f for f in self.facts if f["fact_id"] not in self.answers]

    def fact_for_line(self, line_item_id: Any) -> dict | None:
        return next((f for f in self.facts if f.get("line_item_id") == line_item_id), None)

    def answer_for(self, fact: dict) -> str | None:
        conf = self.answers.get(fact["fact_id"])
        return conf.get("response") if conf else None


def build(case_file_id: str, line_items: list, confirmations: list, case_dos: Any = None) -> FactRegistry:
    facts = stamp(line_items, case_file_id, case_dos)
    by_line = {f.get("line_item_id"): f["fact_id"] for f in facts if f.get("line_item_id")}
    answers: dict[str, dict] = {}
    for c in confirmations or []:
        if not isinstance(c, dict):
            continue
        # a confirmation recorded before fact ids existed is keyed by the row it answered
        fid = c.get("fact_id") or by_line.get(c.get("line_item_id"))
        if fid:
            answers[fid] = c  # the latest answer to a fact wins
    return FactRegistry(facts=facts, answers=answers)


def registry(case: Any) -> FactRegistry:
    return build(
        str(case.case_file_id),
        list(case.line_items or []),
        list(case.encounter_confirmations or []),
        getattr(case, "date_of_service", None),
    )


def merge_confirmations(reg: FactRegistry, new: list[dict]) -> list[dict]:
    """The recorded answers after ``new`` lands: keyed by fact, a re-answer replaces the old
    one, and an answer to a fact not in this submission is KEPT (the submission used to replace
    the whole list — answers recorded by the intake were lost to a later thread submit)."""
    merged: dict[str, dict] = {fid: dict(c) for fid, c in reg.answers.items()}
    for c in new:
        fact = reg.fact_for_line(c.get("line_item_id"))
        # an id no current fact carries (a stale client) is still recorded, under its row
        key = fact["fact_id"] if fact else f"line:{c.get('line_item_id')}"
        merged[key] = {**c, "fact_id": fact["fact_id"] if fact else None}
    return list(merged.values())


def carry_forward(prior: list[dict], fresh: list, case_file_id: str, case_dos: Any = None) -> list[dict]:
    """A re-run's line items, reconciled with the facts the case already had.

    The fresh extraction defines WHICH charges are on the bill now; a fresh charge that is a
    fact the case already had keeps that fact's row — its id, its line_item_id and the wording
    the user answered — so its answer still applies. Matching is by fact_id, then (for a fact
    whose date became known since, or whose position shifted) by the same code among the prior
    facts nothing else claimed. A charge matching nothing is a new fact; a prior fact the fresh
    read no longer contains drops out of the list (its recorded answer stays on file)."""
    prior = stamp(prior, case_file_id, case_dos)
    fresh = stamp(fresh, case_file_id, case_dos)
    by_id = {p["fact_id"]: p for p in prior}
    used: set[str] = set()
    out: list[dict | None] = []
    unmatched: list[tuple[int, dict]] = []
    for f in fresh:
        old = by_id.get(f["fact_id"])
        if old is not None and old["fact_id"] not in used:
            used.add(old["fact_id"])
            out.append(old)
        else:
            unmatched.append((len(out), f))
            out.append(None)
    remaining = [p for p in prior if p["fact_id"] not in used]
    for idx, f in unmatched:
        code = normalize_code(f.get("code"))
        old = next((p for p in remaining if normalize_code(p.get("code")) == code), None)
        if old is not None:
            remaining.remove(old)
            used.add(old["fact_id"])
            out[idx] = old
        else:
            # a new charge — its computed id may be a slot an old fact holds; stamping below
            # gives it the next free occurrence instead
            out[idx] = {**f, "fact_id": None} if f["fact_id"] in used else f
    return stamp([it for it in out if it is not None], case_file_id, case_dos)
