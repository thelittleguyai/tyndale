"""The "See an example" registry and its images stay in step (Brock 2026-09-21, decision 8 — doc 41).

Every ask has a drawn illustration (AI-generated from doc 41's prompts — Phil makes them, Claude Code
cannot) with Brock's numbered legend. Until an image is in the app bundle its entry is
``pending_asset`` and offers nothing new; the SBC and MSN screens keep showing the CMS samples. Three
things must agree, and this guard fails the moment they do not:

  * ``pending_asset`` on the registry entry (runtime/app/intake/examples.py),
  * the file ``apps/mobile/assets/examples/<slot>@2x.png``,
  * the app's build-time manifest (apps/mobile/assets/examples/index.ts).

And no screen ever renders an empty example sheet.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

import pytest

from app.agents.context_loader import load_orchestration_registry
from app.intake import examples as ex_mod
from app.intake.examples import EXAMPLES, example_for

REPO = pathlib.Path(__file__).resolve().parents[2]
ASSETS = REPO / "apps/mobile/assets/examples"
# doc 41's badges per image, in section order
BADGES = {"itemized_bill": 6, "summary_vs_itemized": 1, "insurance_card": 6, "eob": 6, "msn": 5,
          "sbc": 6, "accumulators": 6, "eob_timeline": 2}


def _manifest_slots() -> set[str]:
    """The slots the app's build-time manifest requires (commented lines don't count)."""
    src = (ASSETS / "index.ts").read_text(encoding="utf-8")
    live = "\n".join(line for line in src.splitlines() if not line.strip().startswith(("//", "*", "/*")))
    return {slot for slot, _file in re.findall(r"(\w+)\s*:\s*require\('\./(\w+)\.png'\)", live)}


def test_every_ask_has_its_doc41_illustration_and_legend():
    assert set(EXAMPLES) == set(BADGES)
    registry = load_orchestration_registry()
    for ask, n in BADGES.items():
        e = EXAMPLES[ask]
        assert e.illustration == ask
        assert e.legend_keys == tuple(f"intake.example.{ask}.{i}" for i in range(1, n + 1))
        missing = [k for k in e.legend_keys if k not in registry]
        assert not missing, f"{ask}: legend keys not in the registry: {missing}"
        assert e.aspect == ("landscape" if ask in ("insurance_card", "summary_vs_itemized") else "portrait")


def test_pending_asset_the_file_and_the_app_manifest_agree():
    manifest = _manifest_slots()
    for ask, e in EXAMPLES.items():
        has_file = (ASSETS / f"{e.illustration}@2x.png").exists()
        assert e.pending_asset is (not has_file), (
            f"{ask}: pending_asset={e.pending_asset} but the image file "
            f"{'exists' if has_file else 'is missing'} — flip the flag in app/intake/examples.py"
        )
        assert (e.illustration in manifest) is has_file, (
            f"{ask}: the app manifest (assets/examples/index.ts) and the files on disk disagree"
        )


def test_no_ask_is_offered_with_nothing_to_show():
    for ask, e in EXAMPLES.items():
        offered = example_for(ask)
        if offered is None:
            continue
        assert offered.illustrated or (offered.asset is not None and offered.callout_keys), ask
    # today: every illustration is pending, so exactly the two federal samples are offered
    assert {a for a in EXAMPLES if example_for(a)} == {"sbc", "msn"}


@pytest.mark.parametrize("screen_id", ["bill", "bill_itemized", "eob", "card", "plan_rules", "timeline", "deductible_met", "oop_met"])
def test_no_screen_renders_an_empty_example_sheet(screen_id):
    from app.db.models.case_files import CaseFile
    from app.intake import planner as ip
    from app.intake.render import render_screen

    i = ip.PlannerInputs()
    out = render_screen(screen_id, CaseFile(documents=[], eobs=[], line_items=[]), i, ip.gap_list(i))
    sheet = out.get("example")
    if sheet is None:
        return
    assert sheet["legend"] or (sheet["callouts"] and sheet["asset"]), (screen_id, sheet)


def test_an_illustrated_sheet_carries_brocks_legend_and_its_image_slot(monkeypatch):
    from app.db.models.case_files import CaseFile
    from app.intake import planner as ip
    from app.intake.render import render_screen

    drawn = dataclasses.replace(EXAMPLES["eob"], pending_asset=False)  # as if Phil dropped eob@2x.png
    monkeypatch.setitem(ex_mod.EXAMPLES, "eob", drawn)
    i = ip.PlannerInputs()
    sheet = render_screen("eob", CaseFile(documents=[], eobs=[], line_items=[]), i, ip.gap_list(i))["example"]
    assert sheet["illustration"] == {"slot": "eob", "aspect": "portrait"}
    assert len(sheet["legend"]) == 6 and "allowed amount" in sheet["legend"][2]
    assert sheet["callouts"] == [] and sheet["asset"] is None and sheet["source_line"] is None
    assert "coinsurance" in sheet["glosses"]  # legend 4 uses the term: its gloss rides along


def test_an_illustrated_federal_sample_still_carries_its_fallback(monkeypatch):
    """The app picks by what ITS build bundles: a tab on last week's bundle (no sbc image yet) gets
    the CMS sample's callouts + source line, whole — never a sheet with a button and nothing else."""
    from app.db.models.case_files import CaseFile
    from app.intake import planner as ip
    from app.intake.render import render_screen

    monkeypatch.setitem(ex_mod.EXAMPLES, "sbc", dataclasses.replace(EXAMPLES["sbc"], pending_asset=False))
    i = ip.PlannerInputs()
    sheet = render_screen("plan_rules", CaseFile(documents=[], eobs=[], line_items=[]), i, ip.gap_list(i))["example"]
    assert sheet["illustration"] == {"slot": "sbc", "aspect": "portrait"} and len(sheet["legend"]) == 6
    assert sheet["callouts"] and sheet["asset"]["url"].startswith("https://") and sheet["source_line"]
