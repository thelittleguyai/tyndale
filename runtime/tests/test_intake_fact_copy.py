"""The guided confirmations cards say the code and ONE plain sentence (e2e round 3 R4).

The intake's confirmations screen printed the translate pass's whole clinical paragraph per
charge; the chat-first cap (315733d) never reached it. The split is the app's own
(splitTranslation), held to the same cases; the sentence then runs the intake's grade-5 guard,
and one that fails gives way to the registry's fallback line with the engine's words, whole,
under the disclosure.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from httpx import AsyncClient

from app.agents.context_loader import orchestration_step
from app.intake.fact_copy import MAX_CARD_CHARS, fact_card, split_translation
from app.intake.reading_level import read

CASES = json.loads((pathlib.Path(__file__).parent / "fixtures/line_item_copy_cases.json").read_text())["cases"]
FALLBACK = orchestration_step("intake.confirmations.fact_fallback")


@pytest.mark.parametrize("case", CASES, ids=[c["input"][:30] or "empty" for c in CASES])
def test_the_split_is_the_apps_split(case):
    assert split_translation(case["input"]) == (case["headline"], case["rest"])


def test_a_plain_first_sentence_is_the_card_and_the_rest_waits_under_the_fold():
    card = fact_card({"plain_language_translation": "Blood drawn from your arm. It takes a minute.",
                      "plain_language_context": "Most visits with lab tests include one."}, FALLBACK)
    assert card == {"text": "Blood drawn from your arm.",
                    "more": "It takes a minute.\n\nMost visits with lab tests include one."}


def test_a_clinical_sentence_gives_way_to_the_fallback_and_keeps_every_word_under_the_fold():
    clinical = ("An office or outpatient visit for an established patient, coded at the second-highest "
                "of four standard visit levels, reflecting a moderate level of medical decision-making.")
    card = fact_card({"plain_language_translation": clinical}, FALLBACK)
    assert card["text"] == FALLBACK == "A charge on your bill."
    assert card["more"] == clinical  # the whole engine text, one tap away


def test_a_long_sentence_with_nowhere_to_cut_never_becomes_the_card():
    simple_but_long = " ".join(["the nurse took a look at your arm and then went home"] * 3) + "."
    assert len(simple_but_long) > MAX_CARD_CHARS
    assert fact_card({"plain_language_translation": simple_but_long}, FALLBACK)["text"] == FALLBACK


def test_the_screen_s_own_copy_clears_the_guard():
    assert read(orchestration_step("intake.confirmations.more")).passes()
    assert read(FALLBACK).passes()


@pytest.mark.asyncio
async def test_every_card_on_the_screen_is_one_short_plain_sentence(client: AsyncClient):
    from app.auth.dev_user import resolve_dev_user
    from app.db.base import AsyncSessionLocal
    from app.db.models.case_files import CaseFile

    items = [
        {"line_item_id": "li-a", "code": "99214", "plain_language_translation":
            "An office or outpatient visit for an established patient, coded at the second-highest of four "
            "standard visit levels, reflecting a visit that involved a moderate level of medical decision-making."},
        {"line_item_id": "li-b", "code": "36415", "plain_language_translation": "Blood drawn from your arm.",
         "plain_language_context": "Usually a few minutes."},
    ]
    async with AsyncSessionLocal() as s:
        u = await resolve_dev_user(s)
        cf = CaseFile(
            user_id=u.user_id, status="encounter_verification_pending", intake_mode="guided",
            intake_status="in_progress", line_items=items,
            documents=[{"document_id": "d", "document_type": "itemized_bill", "filename": "b.pdf",
                        "ocr_text": "99214 36415", "extraction_status": "extracted"}],
            # everything before the confirmations is settled, so the planner's next screen is them
            regime_detection={"verified": True}, coverage_regime="erisa_self_funded",
            coverage={"has_secondary_coverage": False},
            intake_state={"acked": ["welcome", "bill_summary", "facts_only"],
                          "skipped": ["eob", "card", "insurer", "plan_rules", "plan_year",
                                      "deductible_met", "oop_met"]},
        )
        s.add(cf)
        await s.commit()
        cfid = str(cf.case_file_id)
    state = (await client.get("/v1/intake/state", params={"case_file_id": cfid})).json()
    assert state["current_step"] == "confirmations", state["current_step"]
    cards = state["screen"]["data"]["line_items"]
    assert [c["code"] for c in cards] == ["99214", "36415"]
    for c in cards:
        assert len(c["text"]) <= MAX_CARD_CHARS and read(c["text"]).passes(), c["text"]
    assert cards[0]["text"] == FALLBACK and "decision-making" in cards[0]["more"]
    assert cards[1] == {**cards[1], "text": "Blood drawn from your arm.", "more": "Usually a few minutes."}
    assert state["screen"]["copy"]["more"] == "Show me what this usually looks like"
