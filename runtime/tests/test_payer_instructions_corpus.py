"""The payer-instructions corpus — the portal guide, ingested (guided Phase 2, item G).

``docs/research/portal_navigation_guide_2026-07-02.md`` feeds "Where to find it" for nine payers.
Its own ship rule holds: a payer path renders only when VERIFIED; the guide's UNVERIFIED items are
stored (``verified=False``) and never rendered — the generic steps show. The no-card branch says
which payers let you sign up without the card (and Tyndale never asks for the number); the BCBS
router asks which Blue only when the card does not say; Admin › Knowledge keeps the quarterly
re-verify clock.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.context_loader import load_orchestration_registry
from app.intake import payer_instructions as pi
from app.intake import planner as ip
from app.intake.render import render_help

GUIDE_PAYERS = {"uhc", "anthem", "aetna", "cigna", "kaiser", "ambetter", "hcsc", "florida_blue", "highmark"}


def _steps(payer_name: str | None, doc: str, **ctx) -> list[str]:
    return render_help(pi.HelpContext(payer_name=payer_name, **ctx), doc)["steps"]


def test_every_guide_payer_is_in_the_corpus_and_every_line_is_registry_copy():
    assert set(pi.PAYERS) == GUIDE_PAYERS
    registry = load_orchestration_registry()
    keys = {k for p in pi.PAYERS.values() for k in (p.sign_in, p.no_card) if k}
    keys |= {k for e in pi.CORPUS for k in e.step_keys} | {pi.BCBS_LOOKUP, pi.BCBS_LOOKUP_PREFIX, pi.SIGN_UP}
    assert not sorted(k for k in keys if k not in registry)
    for e in pi.CORPUS:
        if e.verified:  # checked against the payer's own public pages on the guide's date
            assert e.verified_on == "2026-07-02" and e.step_keys, e
        else:  # stored for the hands-on pass — nothing a member could ever be shown
            assert e.verified_on is None and not e.step_keys and not e.steps and e.claim, e
    # every payer the guide verified something for has at least one member-facing path
    assert {e.payer_id for e in pi.CORPUS if e.verified} == GUIDE_PAYERS - {"ambetter"}


def test_the_guides_unverified_items_are_stored_and_never_rendered():
    unverified = {(e.payer_id, e.document_type) for e in pi.CORPUS if not e.verified}
    # the guide's UNVERIFIED list: document-list and tracker labels for seven payers, two payers'
    # registration fields, two app names, the pharmacy split
    for pid in ("uhc", "anthem", "aetna", "ambetter", "hcsc", "florida_blue", "highmark"):
        assert {(pid, "sbc"), (pid, "accumulators")} <= unverified, pid
    assert {("cigna", "insurance_card"), ("kaiser", "insurance_card"), ("hcsc", "insurance_card"),
            ("florida_blue", "insurance_card"), ("aetna", "eob")} <= unverified
    # where the ONLY entry is unverified, the member gets the general steps — behind the payer's
    # own verified front door, under the "general steps" note
    for pid, doc in sorted(unverified):
        if any(e.verified and (e.payer_id, e.document_type) == (pid, doc) for e in pi.CORPUS):
            continue
        name = {"hcsc": "Blue Cross and Blue Shield of Texas"}.get(pid, pi.PAYERS[pid].name)
        got = pi.instructions_for(doc, None, pi.HelpContext(payer_name=name))
        assert got["scope"] == "generic", (pid, doc)
        if doc in ("sbc", "accumulators", "eob"):
            assert got["step_keys"][0] == pi.PAYERS[pid].sign_in
    anthem = render_help(pi.HelpContext(payer_name="Anthem Blue Cross"), "sbc")
    assert anthem["note"].startswith("These are general steps")
    assert anthem["steps"][0] == "Sign in at anthem.com, or in the Sydney Health app."


def test_a_verified_path_renders_as_the_payers_own():
    kaiser = render_help(pi.HelpContext(payer_name="Kaiser Foundation Health Plan"), "sbc")
    assert kaiser["scope"] == "payer" and kaiser["note"] == "These steps are for Kaiser Permanente."
    assert kaiser["steps"][:2] == [
        "Sign in at kp.org. Pick your area first. Each area's site is a little different.",
        "Go to Benefits. Then pick View benefit summary. Or you can pick Coverage documents. Your SBC is in there.",
    ]
    hcsc = render_help(pi.HelpContext(payer_name="BlueCross BlueShield of Texas"), "accumulators")
    assert hcsc["note"] == "These steps are for BlueCross BlueShield of Texas."  # the member's own plan
    assert "Blue Access for Members lets you check your deductible." in hcsc["steps"]
    # the "as of" date matters to the math: every tracker sheet ends by writing it down
    for pid in ("uhc", "anthem", "aetna", "cigna", "kaiser", "hcsc", "florida_blue", "highmark"):
        entry = pi.PAYER_ENTRIES[(pid, "accumulators", None)]
        assert entry.verified and "intake.help.accumulators_3" in entry.step_keys, pid


def test_the_generic_fallback_is_the_guides_four_step_pattern():
    acc = _steps("Some Regional Plan", "accumulators")
    assert "first page" in acc[1]  # 1 · the home dashboard first
    assert "Benefits, Coverage, or My Plan" in acc[2] and "plan spending" in acc[2]  # 2 · the menus
    sbc = _steps(None, "sbc")
    assert "Benefits, Coverage, or My Plan" in sbc[1] and "Plan Documents" in sbc[2]  # 3 · the documents
    for doc in ("sbc", "accumulators", "eob", "insurance_card"):  # 4 · sign-up prep, then the phone
        assert _steps(None, doc)[-1].startswith("No account yet? Sign up on the site."), doc


@pytest.mark.parametrize(("name", "pid"), [
    ("UnitedHealthcare of Texas, Inc.", "uhc"),
    ("United Healthcare", "uhc"),
    ("Anthem Blue Cross", "anthem"),
    ("Anthem Blue Cross and Blue Shield", "anthem"),
    ("Aetna", "aetna"),
    ("Cigna Healthcare", "cigna"),
    ("Kaiser Foundation Health Plan, Inc.", "kaiser"),
    ("Ambetter from Sunshine Health", "ambetter"),
    ("BlueCross BlueShield of Texas", "hcsc"),
    ("Blue Cross and Blue Shield of Illinois", "hcsc"),
    ("Florida Blue", "florida_blue"),
    ("Highmark Blue Shield", "highmark"),
    ("Highmark Inc.", "highmark"),
    ("Blue Cross Blue Shield", None),  # which Blue? — the router asks
    ("Premera Blue Cross", None),  # a Blue the guide does not cover
    ("Texas Children's Health Plan", None),  # a state places only a BLUE plan
    ("SYNTHETIC MUTUAL HEALTH PLAN", None),
])
def test_names_on_cards_find_their_payer(name, pid):
    assert pi.match_payer(name) == pid


def test_the_bcbs_router_asks_only_when_the_card_does_not_say_which_blue():
    assert pi.needs_blue_router("Blue Cross Blue Shield")
    assert pi.needs_blue_router("BlueCross BlueShield PPO")
    assert pi.needs_blue_router("BCBS")
    assert not pi.needs_blue_router("Premera Blue Cross")  # it names its company: no question
    assert not pi.needs_blue_router("Anthem Blue Cross")  # placed already
    assert not pi.needs_blue_router("Aetna")
    # the guide's map: Anthem states → Anthem; IL/TX/OK/NM/MT → HCSC; FL → Florida Blue;
    # PA/DE/WV/WNY → Highmark; anything else → None (generic + the bcbs.com lookup)
    for plan, pid in [
        ("Anthem Blue Cross Blue Shield", "anthem"),
        ("Blue Cross and Blue Shield of Oklahoma", "hcsc"), ("BCBS of New Mexico", "hcsc"),
        ("BCBSMT", "hcsc"), ("Montana", "hcsc"),
        ("Blue Cross and Blue Shield of Florida", "florida_blue"),
        ("Highmark Blue Cross Blue Shield Delaware", "highmark"), ("West Virginia", "highmark"),
        ("Blue Cross Blue Shield of Western New York", "highmark"), ("Pennsylvania", "highmark"),
        ("Premera Blue Cross", None), ("Blue Cross Blue Shield", None), ("", None),
    ]:
        assert pi.route_blue(plan) == pid, plan


def test_the_no_card_branch_says_what_each_payer_takes_and_never_asks_for_the_number():
    skipped = {"card_on_file": False, "card_skipped": True}
    for name in ("UnitedHealthcare", "Aetna", "Ambetter"):
        last = _steps(name, "sbc", **skipped)[-1]
        assert "Social Security number" in last and "Tyndale never asks" in last, name
    assert "healthsafe-id.com" in _steps("UnitedHealthcare", "accumulators", **skipped)[-1]
    assert "last 4 digits" in _steps("Ambetter", "sbc", **skipped)[-1]
    hcsc = _steps("Blue Cross and Blue Shield of Illinois", "sbc", **skipped)[-1]
    assert "member services number on any bill or EOB" in hcsc and "benefits office" in hcsc
    assert not any("Social Security" in s for s in hcsc.split("\n"))  # the card is required there
    # no line where the guide says nothing, where the card is on file, or before anyone said
    # "I don't have my card" — except on the card's own sheet, which asks exactly that
    assert not any("No card?" in s for s in _steps("Cigna", "sbc", **skipped))
    assert not any("Social Security" in s for s in _steps("Aetna", "sbc"))
    assert not any("Social Security" in s for s in _steps("Aetna", "sbc", card_on_file=False))
    assert "Social Security" in _steps("Aetna", "insurance_card", card_on_file=False)[-1]
    assert not any("Social Security" in s for s in _steps("Aetna", "itemized_bill", **skipped))


def test_no_intake_screen_ever_collects_a_social_security_number():
    from app.db.models.case_files import CaseFile
    from app.intake.render import render_screen

    i = ip.PlannerInputs(coverage={"member_id": "XYZ123456", "payer_name": "Blue Cross Blue Shield"})
    for sc in ip.SCREEN_REGISTRY:
        if sc.kind != "fields":
            continue
        out = render_screen(sc.id, CaseFile(documents=[], eobs=[], line_items=[]), i, ip.gap_list(i))
        for f in out["data"]["fields"]:
            label = out["copy"].get(f["slot"]) or ""
            assert not any(w in (f["name"] + " " + label).lower() for w in ("ssn", "social security")), (sc.id, f)


def test_the_router_is_a_planner_screen_asked_only_while_a_portal_ask_is_ahead():
    # bill, EOB and card in; the card named a Blue but not which one
    base = {"bill_count": 1, "eob_count": 1, "card_present": True, "payer_known": True, "member_id_known": True,
            "population": "commercial", "acked": frozenset({"bill_summary"})}
    unplaced = ip.PlannerInputs(blue_plan_unplaced=True, **base)
    assert ip.next_screen(unplaced) == "blue_plan"  # right after the insurer ask, before the SBC
    assert ip.SCREEN_IDS.index("blue_plan") == ip.SCREEN_IDS.index("insurer") + 1
    assert ip.next_screen(ip.PlannerInputs(**base)) != "blue_plan"
    assert ip.next_screen(ip.PlannerInputs(blue_plan_unplaced=True, skipped=frozenset({"blue_plan"}), **base)) != "blue_plan"
    # nothing left to find on a portal (SBC on file, the EOB stack confirmed): never asked
    done = ip.PlannerInputs(blue_plan_unplaced=True, sbc_on_file=True, completeness_confirmed=True,
                            plan_year_start="2026-01-01", **base)
    assert not ip.applicable("blue_plan", done)


@pytest.mark.asyncio
async def test_the_router_answer_steers_the_sheet_and_the_prefix_never_leaves_the_app(client: AsyncClient, monkeypatch):
    from app.auth.dev_user import resolve_dev_user
    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile

    async def _case() -> str:
        async with AsyncSessionLocal() as s:
            u = await resolve_dev_user(s)
            cf = CaseFile(user_id=u.user_id, status="open", intake_mode="guided", intake_status="in_progress",
                          documents=[], intake_state={"acked": ["welcome"]},
                          coverage={"payer_name": "Blue Cross Blue Shield", "member_id": "ZXQ900112233"})
            s.add(cf)
            await s.commit()
            return str(cf.case_file_id)

    def answer(cid, **values):
        return client.post("/v1/intake/answer", json={"case_file_id": cid, "screen": "blue_plan",
                                                       "action": "continue", "values": values})

    placed = await _case()
    screen = (await client.get("/v1/intake/state", params={"case_file_id": placed, "screen": "blue_plan"})).json()["screen"]
    assert screen["id"] == "blue_plan" and screen["copy"]["body"].endswith(
        "What plan name is on your card, and what are the first 3 letters of your member ID?")
    assert {f["name"]: f["value"] for f in screen["data"]["fields"]} == {"plan_name": None, "id_prefix": "ZXQ"}
    assert (await answer(placed, plan_name="BlueCross BlueShield of Texas", id_prefix="zxq")).status_code == 200
    got = (await client.get("/v1/intake/help", params={"document_type": "accumulators", "case_file_id": placed})).json()
    assert got["scope"] == "payer" and got["payer_name"] == "BlueCross BlueShield of Texas"
    assert got["steps"][0].startswith("Sign in to Blue Access for Members")
    after = (await client.get("/v1/intake/state", params={"case_file_id": placed, "screen": "blue_plan"})).json()
    assert after["screen"]["id"] != "blue_plan"  # answered once, never again

    # a Blue the guide does not cover: the general steps + the bcbs.com lookup, with the prefix
    # the member gave — in the app only
    other = await _case()
    assert (await answer(other, plan_name="Blue Cross Blue Shield", id_prefix="ZXQ")).status_code == 200
    sheet = (await client.get("/v1/intake/help", params={"document_type": "sbc", "case_file_id": other})).json()
    assert sheet["scope"] == "generic" and "Type ZXQ, the first 3 letters of your member ID." in sheet["steps"][-1]
    sent: list[str] = []

    async def _send(to, subject, body, **kw):
        sent.append(body)
        return True

    monkeypatch.setattr("app.notify.email.send_product_email", _send)
    r = await client.post("/v1/intake/help/email", json={"document_type": "sbc", "case_file_id": other, "screen": "plan_rules"})
    assert r.status_code == 200 and sent
    assert "ZXQ" not in sent[0] and "bcbs.com/member-services" in sent[0]  # DL-47: nothing off the card

    # "I'm not sure" is an answer too: the same general steps + lookup, and the screen is done
    skipper = await _case()
    r = await client.post("/v1/intake/answer", json={"case_file_id": skipper, "screen": "blue_plan", "action": "skip", "values": {}})
    assert r.status_code == 200
    sheet = (await client.get("/v1/intake/help", params={"document_type": "sbc", "case_file_id": skipper})).json()
    assert "Look it up with the first 3 letters of your member ID" in sheet["steps"][-1]
    assert (await answer(skipper, plan_name="  ")).status_code == 422


@pytest.mark.asyncio
async def test_admin_knowledge_keeps_the_quarterly_reverify_clock(client: AsyncClient):
    r = await client.get("/v1/admin/knowledge/payer-instructions")
    assert r.status_code == 200
    body = r.json()
    assert body["source"].endswith("portal_navigation_guide_2026-07-02.md") and body["reverify_every_months"] == 3
    assert body["next_due"] == "2026-10-02"  # verified 2026-07-02 + one quarter
    assert body["verified"] == sum(1 for e in pi.CORPUS if e.verified)
    assert body["unverified"] == sum(1 for e in pi.CORPUS if not e.verified)
    uhc = next(p for p in body["payers"] if p["payer_id"] == "uhc")
    shown = [e for e in uhc["entries"] if e["verified"]]
    assert shown and all(e["due_on"] == "2026-10-02" and e["steps"] for e in shown)
    assert all(e["steps"] == [] and e["claim"] for e in uhc["entries"] if not e["verified"])
    assert pi.reverify_due("2026-11-30") == "2027-02-28"  # a quarter on, clamped to the month
