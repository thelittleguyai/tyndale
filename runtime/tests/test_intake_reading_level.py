"""Doc 40 §A6 — fifth-grade reading level, enforced on the copy registry. RATCHETED: every
`intake.*` key must pass from day one; every other key is reported, not failed
(docs/build-kit/reading_level_report.md) — those were authored to a 7th-grade floor and whether
they are rewritten is Brock's call."""

from __future__ import annotations

import pathlib

import pytest

from app.agents.context_loader import load_orchestration_script
from app.intake.reading_level import (
    GRADE_CEILING,
    check_intake_keys,
    count_syllables,
    read,
    terms_used,
)

REPO = pathlib.Path(__file__).resolve().parents[2]


def test_every_shipped_intake_key_reads_at_grade_five():
    problems = check_intake_keys(load_orchestration_script())
    assert problems == [], "intake.* copy above grade 5.9 (doc 40 §A6):\n  " + "\n  ".join(problems)


def test_the_guard_fails_on_a_seeded_bad_key():
    """The check has teeth: a real CO-1A wizard string (what these screens USED to say) fails,
    and the packet's own grade-5 rewrite passes."""
    bad = (
        "Commercial, Medicare, Medicaid, and military coverage each follow different billing and "
        "appeal rules. Getting this right means the numbers and the next steps I give you are accurate."
    )
    good = "We don't know what you'd already paid by then, so we won't guess."
    seeded = {
        **load_orchestration_script(),
        "intake.coverage_type.seeded_bad": f"[A] {bad}",
        "intake.coverage_type.seeded_good": f"[A] {good}",
    }
    problems = [p for p in check_intake_keys(seeded) if "seeded" in p]
    assert len(problems) == 1 and "seeded_bad" in problems[0] and "FK grade" in problems[0], problems
    assert read(bad).grade > GRADE_CEILING >= read(good).grade


def test_a_glossed_term_is_what_made_the_packets_own_bad_example_bad():
    """§A6's example of what NOT to write — "We can't safely assume what your deductible balance
    was" — fails at 6.9 ONLY because of the four-syllable term. With the gloss on the screen the
    term is exempt and the sentence scores 4.7: the formula cannot see that "safely assume" is
    abstract. Recorded so nobody reads a green check as "this copy is good" — it means "this
    copy is not HARD". Voice is still Brock's."""
    example = "We can't safely assume what your deductible balance was at that point in the plan year."
    assert read(example).grade > GRADE_CEILING
    assert read(example, exempt={"deductible"}).grade <= GRADE_CEILING


def test_no_value_carries_markup_from_the_script_file():
    """Found by this guard on its first run: an HTML comment placed BETWEEN keys is parsed into
    the previous key's value (a body runs to the next `## ` heading) — it would have rendered to
    users. Section banners in the script must be `## ` headings, never comments."""
    script = load_orchestration_script()
    dirty = [k for k, v in script.items() if "<!--" in v or "\n## " in v or v.lstrip().startswith("#")]
    assert dirty == []


def test_a_glossed_term_without_its_gloss_on_the_same_screen_fails():
    script = load_orchestration_script()
    # "coinsurance" on a screen that does not carry intake.welcome.gloss_coinsurance
    seeded = {**script, "intake.welcome.seeded": "[A] Your coinsurance is your share of the cost."}
    assert any("seeded" in p and "coinsurance" in p for p in check_intake_keys(seeded))
    # the SAME sentence is fine on the screen that glosses the term
    ok = {**script, "intake.plan_rules_confirm.seeded": "[A] Your coinsurance is your share of the cost."}
    assert not [p for p in check_intake_keys(ok) if "seeded" in p]


def test_a_one_word_button_is_not_scored_as_college_reading():
    """Flesch–Kincaid is defined on prose: "Continue" scores grade 20. Short strings use the
    label rule — no word over three syllables — instead of a formula that does not apply."""
    assert read("Continue").grade is None and read("Continue").passes()
    assert not read("Confirmations").passes()  # four syllables: the segment is "Quick checks"
    assert read("Explanation of Benefits (EOB)", exempt={"eob"}).passes()  # the formal name, glossed


@pytest.mark.parametrize(
    ("word", "n"),
    [("continue", 3), ("deductible", 4), ("share", 1), ("asked", 1), ("wanted", 2), ("paying", 2),
     ("going", 2), ("period", 3), ("annual", 3), ("statement", 2), ("itemized", 3), ("insurer", 3),
     ("identified", 4), ("copies", 2), ("maybe", 2), ("language", 2), ("anyone", 3)],
)  # fmt: skip
def test_the_syllable_counter_on_the_words_our_copy_uses(word, n):
    assert count_syllables(word) == n


def test_term_detection_sees_the_formal_names():
    assert terms_used("Your Explanation of Benefits (EOB) shows the deductible.") == {"eob", "deductible"}
    assert terms_used("What you pay out of pocket") == {"out_of_pocket"}
    assert terms_used("Your plan's rulebook") == set()


def test_the_report_covers_every_non_intake_key_and_fails_nothing():
    """Report-only for the existing keys: the file must list every one (so it cannot go stale
    silently when a key is added), and its own header must say it fails nothing."""
    report = (REPO / "docs/build-kit/reading_level_report.md").read_text(encoding="utf-8")
    missing = [
        k for k in load_orchestration_script() if not k.startswith("intake.") and f"`{k}`" not in report
    ]
    assert missing == [], (
        "reading_level_report.md is stale — run `uv run python scripts/reading_level_report.py`: "
        f"{missing[:5]}"
    )
    assert "Nothing here fails CI" in report


def test_the_committed_reading_level_report_is_current():
    """The report "carries no date on purpose — it changes only when the copy does, so a diff is
    a signal". That only holds if it is regenerated WITH the copy: it shipped one key stale the
    day it was written (263 vs 264). Now a copy change without the report fails here.

        cd runtime && uv run python scripts/reading_level_report.py
    """
    import importlib.util
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("reading_level_report", root / "scripts/reading_level_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.OUT.read_text(encoding="utf-8") == mod.build(), (
        "docs/build-kit/reading_level_report.md is stale — regenerate it (see this test's docstring)"
    )

