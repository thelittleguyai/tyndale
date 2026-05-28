# Partial FHIR data (graceful-degradation playbook)

> mode: full-only — the FHIR-specific degradation path. Mirrors the V1-Lite `value_with_incomplete_data.md` so behavior is identical across modes.

**What this covers.** What Tyndale can still do when a FHIR pull returns only some resources.

**Common partial states + what to do.**
- **Coverage present, EOB not yet posted:** run everything that needs only coverage terms +
  the bill — code-level checks (bundling, upcoding, duplicates, MUE, modifiers, phantom via
  encounter verification), price benchmarking, and "here's what you SHOULD owe given your
  benefits." State clearly: "your insurer hasn't posted the EOB for this visit yet."
- **EOB present, Coverage thin:** parse the EOB's claimed figures but flag that the
  independent computation is limited until the coverage terms are confirmed (ask the user or
  pull the SBC).
- **Clinical notes unavailable:** fall back to user encounter verification
  (`bill_error_detection/06_encounter_verification/`).

**Auto-re-check.** Tell the user what's pending and that Tyndale will re-check automatically
(ties into the Proactive Monitor cron). Give an expected timeframe when known.

**The rule.** Show value first; never dead-end the user because a resource is missing.
