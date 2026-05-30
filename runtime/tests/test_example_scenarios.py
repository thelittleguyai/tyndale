"""Phase 2L — example-scenario quality + category mapping.

The deterministic scenarios_for() generator is exercised directly (it's the
no-real-Claude path that produces the scenarios the encounter UI shows in dev +
the fixture/backfill floor). Asserts the prompt's quality bars: 3-5 per item,
factual (no clinical judgment), second-person past tense, category-aware, and a
minimal generic set for unknown codes.
"""

from __future__ import annotations

from app.agents.example_scenarios import backfill_scenarios, scenarios_for

_CLINICAL_JUDGMENT = [
    "should have",
    "should you",
    "necessary",
    "appropriate",
    "did you need",
    "was this needed",
]


def _assert_factual(scenarios: list[str]) -> None:
    for s in scenarios:
        low = s.lower()
        for phrase in _CLINICAL_JUDGMENT:
            assert phrase not in low, f"clinical-judgment phrase '{phrase}' in: {s}"


def test_translate_mode_produces_3_to_5_scenarios_per_line_item():
    for code in ["99285", "99213", "80053", "70553", "44970", "G0008", "E0601"]:
        cs = "HCPCS" if code[0].isalpha() else "CPT"
        n = len(scenarios_for(code, cs))
        assert 3 <= n <= 5, f"{code}: {n} scenarios"


def test_scenarios_are_factual_not_clinical_judgment():
    for code in ["99285", "99213", "80053", "70553", "44970", "G0008", "E0601", "ZZZ999"]:
        cs = "HCPCS" if code[0].isalpha() else "CPT"
        _assert_factual(scenarios_for(code, cs))


def test_scenarios_second_person_past_tense():
    for code in ["99285", "80053", "70553", "44970"]:
        s = scenarios_for(code)
        assert all("you" in x.lower() for x in s), f"{code}: a scenario doesn't address 'you'"
        joined = " ".join(s).lower()
        assert "you'd" in joined or "you would" in joined or "you may have" in joined


def test_high_risk_em_visit_gets_em_category_scenarios():
    s = " ".join(scenarios_for("99285")).lower()  # high-complexity ER E/M
    assert "hour" in s or "spent" in s  # duration
    assert "staff" in s or "nurse" in s or "doctor" in s  # who you saw
    assert "test" in s or "blood" in s or "imaging" in s  # tests done


def test_unknown_code_gets_minimal_generic_scenarios():
    s = scenarios_for("ZZZ999", "HCPCS")  # unrecognized → generic, not fabricated specifics
    assert 2 <= len(s) <= 3
    joined = " ".join(s).lower()
    for specific in ["mri", "anesthesia", "blood drawn", "scanner", "vaccine"]:
        assert specific not in joined, f"fabricated specific '{specific}' for an unknown code"


def test_backfill_fills_missing_and_preserves_existing():
    items = [
        {"code": "99285", "code_system": "CPT"},  # missing → filled
        {"code": "70553", "example_scenarios": ["already here"]},  # preserved
    ]
    backfill_scenarios(items)
    assert len(items[0]["example_scenarios"]) >= 3
    assert items[1]["example_scenarios"] == ["already here"]
