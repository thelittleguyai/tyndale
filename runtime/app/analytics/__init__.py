"""Internal analytics (P0, Brock's dashboard spec 2026-07-11).

Four binding design rules, encoded as constraints (not conventions):

1. Every rate names its denominator — the aggregates schema (`analytics_daily`) stores
   numerator, denominator, and a pinned definition string per ratio; a ratio without a
   definition fails validation. See ``app.analytics.definitions``.
2. PHI-free by construction — ONE ``analytics_events`` table; properties are validated against
   a per-event-type schema of enums / numbers / booleans ONLY. There is no free-text property
   type anywhere, so a "string that isn't an enum" is unrepresentable. See ``app.analytics.events``.
3. First-party only — Plausible was removed from the authenticated app; funnel truth is emitted
   server-side wherever the fact is server-known (``app.analytics.emit``).
4. Counts before ratios — a rendering rule enforced in the admin dashboard.
"""
