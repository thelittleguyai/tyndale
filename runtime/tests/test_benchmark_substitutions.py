"""Benchmark substitutions (Brock 2026-08-22, §2.1) — Tier 3, range only, tombstones dark."""

from __future__ import annotations

import pytest

from app.sources.materiality import disclosure_tier
from app.sources.missing_data_priors import (
    BENCHMARK_SUBSTITUTIONS,
    benchmark_point,
    benchmark_range,
)


def test_active_benchmarks_yield_ranges_with_provenance():
    low, high, meta = benchmark_range("hospital_outpatient_pct_medicare")
    assert (low, high) == (1.65, 3.00) and meta.base == 2.79
    assert "RAND" in meta.source and meta.as_of == "2024-12" and meta.tier3_only
    low, high, meta = benchmark_range("physician_pct_medicare")
    assert (low, high) == (1.18, 1.79) and "MedPAC" in meta.source
    _, _, imaging = benchmark_range("imaging_pct_medicare")
    assert "LOW confidence" in imaging.note  # Tier-3 language only


@pytest.mark.parametrize("key", ["lab_pct_medicare", "regional_average_substitution"])
def test_tombstoned_entries_produce_no_number_even_if_queried(key):
    """Brock's explicit instruction: these MUST stay dark. Even a direct query yields
    nothing user-visible — no range, and the point accessor refuses on principle."""
    entry = BENCHMARK_SUBSTITUTIONS[key]
    assert entry.tombstone and not entry.active
    assert benchmark_range(key) is None
    with pytest.raises(TypeError, match="never a point"):
        benchmark_point(key)


def test_no_benchmark_ever_renders_point_form():
    for key in BENCHMARK_SUBSTITUTIONS:
        with pytest.raises(TypeError):
            benchmark_point(key)
    assert benchmark_range("no_such_key") is None


def test_tier3_is_forced_for_any_benchmark_substitution():
    # Even a zero-width, immaterial figure is Tier 3 the moment a benchmark is its basis.
    assert disclosure_tier(0.0, 100.0, benchmark_substitution=True) == 3
    assert disclosure_tier(5.0, 5000.0, benchmark_substitution=True) == 3
    # And the flag defaults off — ordinary tiers are unchanged.
    assert disclosure_tier(0.0, 100.0) == 0
