"""US states + DC — the jurisdiction vocabulary (2026-08-19, settings item 2).

The single Python source for the profile `state` field and (seed-era) state-law
jurisdiction selection. The TS mirror lives in packages/shared/src/us-states.ts — keep
them identical (the enum-map discipline every other shared vocabulary follows).
"""

from __future__ import annotations

US_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY",
})
