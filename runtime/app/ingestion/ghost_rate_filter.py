"""TiC ghost-rate filtering + confidence scoring (Phase CO-3A, DL-63).

~84-92% of Transparency-in-Coverage rows are "ghost rates" — values a payer
publishes for codes a provider never bills, or boilerplate placeholders. They
must be filtered before any TiC data informs a user-facing estimate.

DL-63 is an explicit STARTING POSTURE: the thresholds + weights here are tunable
once real estimates can be compared against real bills. Keep this module the one
place those knobs live.
"""

from __future__ import annotations

import math

# DL-63 starting thresholds.
_MIN_RATIO = 0.30  # rate must be >= 30% of Medicare allowable
_MAX_RATIO = 5.00  # ... and <= 500%
_MIN_CORROBORATION = 2  # single-occurrence rates are usually ghost


def is_likely_ghost(
    rate: float,
    medicare_allowable: float | None,
    corroborating_source_count: int,
) -> bool:
    """True if the rate looks like a ghost (DL-63). Any single signal => ghost.

    - rate <= 0
    - (when a Medicare baseline is known) rate outside 30%-500% of it
    - present in fewer than 2 distinct payer files (single-occurrence)
    """
    if rate is None or rate <= 0:
        return True
    if medicare_allowable and medicare_allowable > 0:
        ratio = rate / medicare_allowable
        if ratio < _MIN_RATIO or ratio > _MAX_RATIO:
            return True
    if corroborating_source_count < _MIN_CORROBORATION:
        return True
    return False


def confidence_score(
    rate: float,
    medicare_allowable: float | None,
    corroborating_source_count: int,
    record_age_days: int,
) -> float:
    """Weighted confidence in [0,1] for a surviving rate (DL-63 formula).

    base 0.5; +0.1 per corroborating source (cap 5 => +0.5); penalize distance
    from the Medicare baseline (log10 ratio); decay 0.001/day after 90 days.
    """
    score = 0.5
    score += 0.1 * min(max(corroborating_source_count, 0), 5)
    if medicare_allowable and medicare_allowable > 0 and rate and rate > 0:
        score -= 0.2 * abs(math.log10(rate / medicare_allowable))
    score -= 0.001 * max(0, record_age_days - 90)
    return max(0.0, min(1.0, round(score, 4)))
