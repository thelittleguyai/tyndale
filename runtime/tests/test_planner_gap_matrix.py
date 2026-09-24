"""The planner's gap list covers every input the OOP math needs (guided Phase 2, item H — doc 44).

docs/research/tyndale_oop_calculation_method.md Part 1 lists what the independent figure rests on
(groups A–E). docs/build-kit/44_planner_gap_matrix.md says, for each, whether the planner ASKS it,
INFERS it from a document, or the audit SILENTLY defaults it (the Tier 0–3 ladder), and on which
screen. The audit found two dimensions the gap list did not carry — the allowed-amount source
and network status — and added them. This guard keeps the matrix and the planner in step.
"""

from __future__ import annotations

import datetime
import pathlib
import re
from types import SimpleNamespace

import pytest

from app.intake import planner as ip
from app.intake.snapshot import _allowed_amount_known, _network_status

MATRIX = pathlib.Path(__file__).resolve().parents[2] / "docs/build-kit/44_planner_gap_matrix.md"
# every input Part 1 lists (A claim · B plan design · C accumulators · D patient · E encounter)
PART_1 = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "B1", "B2", "B3", "B4", "B5", "B6", "B7",
          "B8", "B9", "C1", "C2", "C3", "D1", "D2", "D3", "D4", "E1")  # fmt: skip
HOW = ("inferred", "asked", "silent", "not captured")


def _rows() -> dict[str, dict]:
    rows = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"[A-E]\d+", cells[0]):
            keys = {k.strip(" `") for k in cells[3].split(",") if k.strip(" `—")}
            screens = {s.strip() for s in cells[4].split(",") if s.strip() not in ("", "—")}
            rows[cells[0]] = {"how": cells[2], "keys": keys, "screens": screens}
    return rows


def _code_gaps() -> dict[str, set[str]]:
    """gap key -> every screen the planner points it at (the payer ask moves once a card lands)."""
    out: dict[str, set[str]] = {}
    for i in (ip.PlannerInputs(bill_count=1), ip.PlannerInputs(bill_count=1, card_present=True)):
        for g in ip.gap_list(i).gaps:
            out.setdefault(g.key, set()).add(g.screen)
    return out


def test_every_part_1_input_has_a_row_and_a_rung_of_the_ladder():
    rows = _rows()
    assert not [x for x in PART_1 if x not in rows], "a Part 1 input lost its row in doc 44"
    for rid, r in rows.items():
        assert any(h in r["how"] for h in HOW), f"{rid}: '{r['how']}' is not on the ladder"


def test_the_matrix_and_the_planner_agree_on_every_gap_and_its_screen():
    rows, code = _rows(), _code_gaps()
    documented = {k for r in rows.values() for k in r["keys"]}
    assert not sorted(set(code) - documented), "a planner gap is missing from doc 44"
    assert not sorted(documented - set(code)), "doc 44 names a gap the planner does not have"
    for rid, r in rows.items():
        assert r["screens"] <= set(ip.SCREEN_IDS), f"{rid}: unknown screen {r['screens'] - set(ip.SCREEN_IDS)}"
        if r["keys"]:
            want = set().union(*(code[k] for k in r["keys"]))
            assert r["screens"] == want, f"{rid}: doc 44 says {r['screens']}, the planner says {want}"


def _gap(i: ip.PlannerInputs, key: str) -> ip.Gap:
    return ip.gap_list(i).get(key)


def test_the_allowed_amount_is_a_gap_only_the_eob_can_close():
    assert _gap(ip.PlannerInputs(), "allowed_amount").state == "not_needed"  # no claim yet
    open_ = _gap(ip.PlannerInputs(bill_count=1), "allowed_amount")
    assert (open_.state, open_.screen, open_.limits, open_.load_bearing) == (
        "unresolved", "eob", "intake.limits.no_allowed_amount", True)
    assert _gap(ip.PlannerInputs(bill_count=1, skipped=frozenset({"eob"})), "allowed_amount").state == "skipped"
    done = _gap(ip.PlannerInputs(bill_count=1, eob_count=1, allowed_amount_known=True), "allowed_amount")
    assert (done.state, done.provenance) == ("resolved", "document")
    # an EOB that did not state it asks for nothing more — the readiness line says what it costs
    assert ip.next_screen(ip.PlannerInputs(bill_count=1, eob_count=1)) != "eob"


def test_network_status_is_read_off_the_eob_and_never_asked():
    for said in ("in", "out"):
        g = _gap(ip.PlannerInputs(eob_count=1, network_status=said), "network_status")
        assert (g.state, g.provenance) == ("resolved", "document")
    g = _gap(ip.PlannerInputs(bill_count=1), "network_status")
    assert (g.state, g.load_bearing, g.limits) == ("unresolved", False, "intake.limits.network_assumed")
    assert not any(s.id == "network_status" for s in ip.SCREEN_REGISTRY)  # no screen asks it


def test_the_snapshot_reads_both_from_the_seams_the_audit_uses():
    def case(*docs, dos=None):
        return SimpleNamespace(documents=list(docs), date_of_service=dos)

    eob = {"document_type": "eob", "ocr_text": "EXPLANATION OF BENEFITS  Billed $185.00  Allowed $120.00"}
    no_allowed = {"document_type": "eob", "ocr_text": "EXPLANATION OF BENEFITS  Billed $185.00  You owe $24.00"}
    assert _allowed_amount_known(case(eob)) and not _allowed_amount_known(case(no_allowed))
    assert not _allowed_amount_known(case({"document_type": "bill", "ocr_text": "Allowed $120.00"}))
    visit = datetime.date(2026, 3, 14)
    rows = [{"date": "2026-01-09", "network": "out"}, {"date": "2026-03-14", "network": "in"}]
    assert _network_status(case(dos=visit), rows) == "in"  # THIS visit's EOB, not January's
    assert _network_status(case(dos=None), rows) == "out"  # no visit date: any "out" wins
    assert _network_status(case(dos=visit), [{"date": "2026-03-14", "network": None}]) is None


@pytest.mark.asyncio
async def test_the_readiness_screen_says_what_each_new_gap_limits():
    from app.db.models.case_files import CaseFile
    from app.intake.render import render_screen

    i = ip.PlannerInputs(bill_count=1, eob_count=1, network_status="in")
    lines = {x["key"]: x for x in render_screen("readiness", CaseFile(documents=[], eobs=[], line_items=[]),
                                                i, ip.gap_list(i))["data"]["lines"]}
    allowed = lines["allowed_amount"]
    assert allowed["label"] == "Your plan's price for each charge" and not allowed["resolved"]
    assert allowed["limits"].startswith("I don't have your plan's price for each charge.")
    assert lines["network_status"]["resolved"] and lines["network_status"]["limits"] is None
