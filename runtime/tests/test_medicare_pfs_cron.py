"""Medicare PFS cron — DL-67 conversion-factor staleness warning.

The CF (DEFAULT_CONVERSION_FACTOR in app.ingestion.parsers.medicare_pfs) is hardcoded
per year; DL-67 requires the cron to warn loudly when MEDICARE_CF_EFFECTIVE_YEAR no
longer matches the current calendar year so the annual operational bump isn't missed.
"""

from __future__ import annotations

import logging

from app.crons.medicare_pfs_cron import MEDICARE_CF_EFFECTIVE_YEAR, _check_cf_freshness


def test_cf_freshness_warns_when_year_mismatch(caplog):
    # Inject a current year one past the effective CF year (e.g. 2027 vs 2026).
    with caplog.at_level(logging.WARNING):
        _check_cf_freshness(current_year=MEDICARE_CF_EFFECTIVE_YEAR + 1)
    assert "Medicare CF stale" in caplog.text
    assert str(MEDICARE_CF_EFFECTIVE_YEAR) in caplog.text
    assert str(MEDICARE_CF_EFFECTIVE_YEAR + 1) in caplog.text


def test_cf_freshness_silent_when_year_matches(caplog):
    with caplog.at_level(logging.WARNING):
        _check_cf_freshness(current_year=MEDICARE_CF_EFFECTIVE_YEAR)
    assert "Medicare CF stale" not in caplog.text
