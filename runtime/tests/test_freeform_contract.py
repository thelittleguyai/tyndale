"""Freeform response contract (Brock 2026-08-22, items 2 + 5) — the eval-style validator.

Sampled responses are judged by the same pure function the runtime counts with, so the
"super long" answer and the pipe table fail HERE before they fail on a phone.
"""

from __future__ import annotations

from app.agents.chat_contract import (
    freeform_contract_violations,
    unsubstantiated_stat_in_tier_a,
    word_count,
)

_CLEAN = (
    "A deductible is the amount you pay for covered care before your plan starts paying. "
    "After you meet it, you usually pay a copay or coinsurance instead. "
    "Do you want me to explain how it interacts with your out-of-pocket maximum?"
)

_LONG = " ".join(["word"] * 250)

_TABLE = (
    "Here are the terms:\n\n| Term | Meaning |\n|---|---|\n| Copay | flat fee |\n\n"
    "Which applies to you?"
)

_BROCK_SCREENSHOT_SAMPLE = (
    "Unfortunately, studies have found error rates as high as 80% on hospital bills, "
    "so it is worth checking every line."
)


def test_clean_mobile_first_answer_passes():
    assert word_count(_CLEAN) <= 120
    assert freeform_contract_violations(_CLEAN) == []


def test_super_long_answer_fails():
    assert "over_length" in freeform_contract_violations(_LONG)


def test_pipe_table_fails():
    assert "table" in freeform_contract_violations(_TABLE)


def test_too_many_lists_or_items_or_questions_fail():
    two_lists = "- a\n- b\n\nthen\n\n- c\n- d"
    assert "multiple_lists" in freeform_contract_violations(two_lists)
    long_list = "\n".join(f"{i}. item" for i in range(1, 7))
    assert "list_too_long" in freeform_contract_violations(long_list)
    assert "multiple_questions" in freeform_contract_violations("Why? And how? Really?")


def test_item5_unsubstantiated_stat_in_tier_a_fails_validation():
    chunks = [{"tier": "A", "text": _BROCK_SCREENSHOT_SAMPLE, "citations": []}]
    assert unsubstantiated_stat_in_tier_a(chunks)  # the 80% pattern, delivered as fact


def test_item5_cited_tier_b_stat_is_allowed_and_qualitative_tier_a_passes():
    cited = [{"tier": "B", "text": _BROCK_SCREENSHOT_SAMPLE, "citations": [{"source_id": "s"}]}]
    assert unsubstantiated_stat_in_tier_a(cited) == []
    qualitative = [{"tier": "A", "text": "Billing errors are common, so it is worth checking."}]
    assert unsubstantiated_stat_in_tier_a(qualitative) == []
    # A percentage with NO error claim (a coinsurance rate) is fine in tier A.
    rate = [{"tier": "A", "text": "Coinsurance of 20% means you pay a fifth of the allowed amount."}]
    assert unsubstantiated_stat_in_tier_a(rate) == []


# ── item 3 (2026-08-22): the failure copy is banned, any tier ──────────────────────────
from app.agents.chat_contract import freeform_banned_phrase_hits  # noqa: E402

_FIELD_TEST_FAILURE = (
    "I'm currently in freeform chat mode and can't create a case for you directly. "
    "You'll need to use the case creation flow to upload your documents."
)


def test_field_test_failure_copy_is_banned():
    hits = freeform_banned_phrase_hits(_FIELD_TEST_FAILURE)
    assert "freeform chat mode" in hits
    assert any("create a case" in h for h in hits)
    assert any("case creation flow" in h for h in hits)


def test_the_right_reply_is_clean():
    assert freeform_banned_phrase_hits("Let's get your case started — tap below to upload your bill.") == []
