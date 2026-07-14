"""Free-text verification mapper (D4b, DL-91). The deterministic layer is precision-first: it maps
the clean cases and DEFERS (mappable=False, or None→Haiku) on anything ambiguous or partial — a
half-right pre-selection teaches distrust. Haiku is disabled here (no creds), so an un-mappable
utterance returns mappable=False."""

from __future__ import annotations

import pytest

from app.agents.verification_mapper import Card, _deterministic, map_verification

# Two MRIs (the duplicate-CPT shape) + a blood draw.
CARDS = [
    Card(line_item_id="li1", ordinal=1, code="70553", description="MRI brain with contrast", amount=1850.0),
    Card(line_item_id="li2", ordinal=2, code="73721", description="MRI knee without contrast", amount=1200.0),
    Card(line_item_id="li3", ordinal=3, code="36415", description="blood draw", amount=25.0),
]


def _by_id(result):
    return {m.line_item_id: m.intended_answer for m in result.mappings}


@pytest.mark.parametrize(
    "utterance,expected,mappable",
    [
        # ordinals
        ("the second one is wrong", {"li2": "no"}, True),
        ("the first one is right", {"li1": "yes"}, True),
        ("I'm not sure about the third one", {"li3": "unsure"}, True),
        # code / amount / description references
        ("the 73721 never happened", {"li2": "no"}, True),
        ("the $1,850 one is right", {"li1": "yes"}, True),
        ("the blood draw didn't happen", {"li3": "no"}, True),
        # universals
        ("all of those are right", {"li1": "yes", "li2": "yes", "li3": "yes"}, True),
        ("none of that happened", {"li1": "no", "li2": "no", "li3": "no"}, True),
        # compound negation
        ("the first one is right but not the second", {"li1": "yes", "li2": "no"}, True),
        # explicit conjunction, both resolve
        ("the first and the second are wrong", {"li1": "no", "li2": "no"}, True),
        # mixed message — map the verification part, ignore the question (map-only, D4b note)
        ("the second one is wrong — also what's a deductible?", {"li2": "no"}, True),
    ],
)
def test_deterministic_maps(utterance, expected, mappable):
    r = _deterministic(utterance, CARDS)
    assert r is not None, "expected a deterministic result"
    assert _by_id(r) == expected
    assert r.mappable is mappable
    assert r.method == "deterministic"


@pytest.mark.parametrize(
    "utterance",
    [
        "that one didn't happen",  # ambiguous — no referent resolves against 3 cards
        "the mri and the ultrasound didn't happen",  # ultrasound isn't a card → conjunction defer
        "asdf qwer zxcv",  # gibberish
        "hmm",  # no polarity, no referent
    ],
)
def test_deterministic_defers_when_unsure(utterance):
    # precision-first: returns None (→ Haiku) rather than a subset pre-selection.
    assert _deterministic(utterance, CARDS) is None


@pytest.mark.asyncio
async def test_map_verification_falls_back_without_haiku(monkeypatch):
    # deterministic can't resolve + Haiku disabled → mappable=False (the caller shows the nudge)
    r = await map_verification("that one didn't happen", CARDS)
    assert r.mappable is False and not r.mappings


@pytest.mark.asyncio
async def test_map_verification_deterministic_wins(monkeypatch):
    r = await map_verification("the second one is wrong", CARDS)
    assert r.method == "deterministic" and _by_id(r) == {"li2": "no"} and r.mappable


def test_confidence_and_partial_policy():
    from app.agents.verification_mapper import Mapping, _finalize

    # addressed 3 but only 2 mapped → partial → NOT mappable (never pre-select a subset)
    r = _finalize([Mapping("a", "no", 0.95), Mapping("b", "no", 0.95)], addressed=3, method="haiku")
    assert r.partial and not r.mappable
    # all addressed items mapped, high confidence → mappable
    r2 = _finalize([Mapping("a", "no", 0.95)], addressed=1, method="haiku")
    assert r2.mappable and not r2.partial
    # a low-confidence mapping is dropped → nothing to pre-select → fallback
    r3 = _finalize([Mapping("a", "no", 0.4)], addressed=1, method="haiku")
    assert not r3.mappable and not r3.mappings
