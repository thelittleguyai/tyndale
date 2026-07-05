"""Appeal deadline engine + escalation state machine (Sprint G, shadow-mode). Pure date math
with boundary cases, and the ladder's allowed transitions."""

from __future__ import annotations

from datetime import date

import pytest

from app.appeals.deadlines import (
    DEADLINE_RULES,
    UnknownDeadlineRule,
    add_months,
    compute_deadline,
    deadline_date,
)
from app.appeals.tracks import (
    APPEAL_STATES,
    InvalidAppealTransition,
    can_transition,
    is_terminal,
    is_valid_state,
    next_states,
)


# --- deadline table ---
def test_deadline_windows_match_the_memo():
    assert DEADLINE_RULES["erisa_internal_appeal"].days == 180
    assert DEADLINE_RULES["aca_internal_appeal"].days == 180
    assert DEADLINE_RULES["ma_reconsideration"].days == 65  # NOT 60
    assert DEADLINE_RULES["federal_external_review"].months == 4
    assert DEADLINE_RULES["ppdr"].days == 120
    assert DEADLINE_RULES["ppdr"].dollar_threshold == 400.0


@pytest.mark.parametrize(
    "rule,trigger,expected",
    [
        ("erisa_internal_appeal", date(2026, 1, 1), date(2026, 6, 30)),  # +180d
        ("ma_reconsideration", date(2026, 3, 1), date(2026, 5, 5)),  # +65d
        ("federal_external_review", date(2026, 1, 15), date(2026, 5, 15)),  # +4 months
        ("ppdr", date(2026, 1, 1), date(2026, 5, 1)),  # +120d
    ],
)
def test_deadline_dates(rule, trigger, expected):
    assert deadline_date(rule, trigger) == expected


def test_add_months_clamps_to_month_end():
    # Jan 31 + 1 month → Feb 28 (2026 is not a leap year).
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    # Oct 31 + 4 months → Feb 28.
    assert add_months(date(2025, 10, 31), 4) == date(2026, 2, 28)
    # Year rollover.
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_compute_deadline_boundary():
    # ERISA 180d from Jan 1 → Jun 30. On the deadline day: 0 remaining, not expired.
    on_deadline = compute_deadline("erisa_internal_appeal", date(2026, 1, 1), date(2026, 6, 30))
    assert on_deadline.days_remaining == 0
    assert on_deadline.expired is False
    # The day after: expired.
    after = compute_deadline("erisa_internal_appeal", date(2026, 1, 1), date(2026, 7, 1))
    assert after.days_remaining == -1
    assert after.expired is True


def test_unknown_rule_raises():
    with pytest.raises(UnknownDeadlineRule):
        deadline_date("not_a_rule", date(2026, 1, 1))


# --- escalation ladder ---
def test_ladder_transitions():
    assert can_transition("call", "supervisor")
    assert can_transition("supervisor", "internal_appeal")
    assert can_transition("internal_appeal", "external_review")
    assert can_transition("external_review", "cms_or_state_complaint")
    # No skipping and no going backward.
    assert not can_transition("call", "internal_appeal")
    assert not can_transition("supervisor", "call")
    assert not can_transition("cms_or_state_complaint", "external_review")


def test_next_states_and_terminal():
    assert next_states("call") == ("supervisor",)
    assert next_states("cms_or_state_complaint") == ()
    assert is_terminal("cms_or_state_complaint")
    assert not is_terminal("call")
    for s in APPEAL_STATES:
        assert is_valid_state(s)
    assert not is_valid_state("nope")


def test_invalid_transition_exception_shape():
    exc = InvalidAppealTransition("call", "external_review")
    assert exc.from_state == "call" and exc.to_state == "external_review"
