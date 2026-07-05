"""Appeal-deadline engine (Sprint G, shadow-mode DL-55/56).

Per-plan-type clock table + pure, timezone-safe date math. This is the skeleton of Brock's
full playbook — the known deadlines are seeded here; the rest lands with
``TODO(brock-content: medical_necessity_appeal_playbook_2026-07-03.md)``.

Seeded deadlines:
  * ERISA / ACA internal appeal — 180 days from the adverse benefit determination.
  * Medicare Advantage reconsideration — 65 days (NOT 60) from the notice.
  * Federal external review — 4 months from the final internal denial.
  * Provider payment dispute resolution (PPDR) — 120 days, with a $400 amount-in-dispute
    threshold.

Nothing here sends anything or persists state; it computes clocks. All functions are pure
and take an explicit reference date so they are deterministic and timezone-safe (callers
pass a ``date``; a ``datetime`` is normalized to its UTC date).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    return value


def add_days(start: date | datetime, days: int) -> date:
    from datetime import timedelta

    return _as_date(start) + timedelta(days=days)


def add_months(start: date | datetime, months: int) -> date:
    """Month arithmetic that clamps to the last valid day (e.g. Jan 31 + 1mo → Feb 28/29)."""
    d = _as_date(start)
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp the day to the target month's length.
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - _one_day()).day
    return date(year, month, min(d.day, last_day))


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)


@dataclass(frozen=True)
class DeadlineRule:
    rule_id: str
    label: str
    days: int | None = None
    months: int | None = None
    dollar_threshold: float | None = None  # e.g. PPDR's $400 amount-in-dispute floor
    as_of: str = "2026-07-03"
    source: str = "Batch-1 memo"
    note: str = ""


# Keyed by rule_id. TODO(brock-content: medical_necessity_appeal_playbook_2026-07-03.md) —
# the full per-plan-type playbook (populations, sub-steps, evidence windows) drops in here.
DEADLINE_RULES: dict[str, DeadlineRule] = {
    "erisa_internal_appeal": DeadlineRule(
        "erisa_internal_appeal", "ERISA/ACA internal appeal", days=180,
        note="180 days from the adverse benefit determination (29 C.F.R. 2560.503-1).",
    ),
    "aca_internal_appeal": DeadlineRule(
        "aca_internal_appeal", "ACA internal appeal", days=180,
        note="180 days; mirrors the ERISA internal-appeal window for ACA-market plans.",
    ),
    "ma_reconsideration": DeadlineRule(
        "ma_reconsideration", "Medicare Advantage reconsideration", days=65,
        note="65 days (NOT 60) from the MA plan's organization determination notice.",
    ),
    "federal_external_review": DeadlineRule(
        "federal_external_review", "Federal external review", months=4,
        note="4 months from the final internal denial to request external review.",
    ),
    "ppdr": DeadlineRule(
        "ppdr", "Provider payment dispute resolution", days=120, dollar_threshold=400.0,
        note="120-day filing window; $400 minimum amount-in-dispute threshold.",
    ),
}


@dataclass(frozen=True)
class DeadlineComputation:
    rule_id: str
    label: str
    trigger_date: str
    deadline_date: str
    days_remaining: int
    expired: bool
    dollar_threshold: float | None
    note: str


class UnknownDeadlineRule(Exception):
    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"unknown appeal-deadline rule: {rule_id!r}")


def deadline_date(rule_id: str, trigger: date | datetime) -> date:
    """The absolute deadline for ``rule_id`` counted from ``trigger``."""
    rule = DEADLINE_RULES.get(rule_id)
    if rule is None:
        raise UnknownDeadlineRule(rule_id)
    if rule.months is not None:
        return add_months(trigger, rule.months)
    return add_days(trigger, rule.days or 0)


def compute_deadline(
    rule_id: str, trigger: date | datetime, as_of: date | datetime
) -> DeadlineComputation:
    """Full clock for a rule: the deadline, days remaining (>=0 or negative when past),
    and whether it has expired as of ``as_of``. Timezone-safe (dates only)."""
    rule = DEADLINE_RULES.get(rule_id)
    if rule is None:
        raise UnknownDeadlineRule(rule_id)
    dl = deadline_date(rule_id, trigger)
    ref = _as_date(as_of)
    remaining = (dl - ref).days
    return DeadlineComputation(
        rule_id=rule_id,
        label=rule.label,
        trigger_date=_as_date(trigger).isoformat(),
        deadline_date=dl.isoformat(),
        days_remaining=remaining,
        expired=ref > dl,
        dollar_threshold=rule.dollar_threshold,
        note=rule.note,
    )
