# FAIR Health UCR lookup

**Purpose.** Get the usual, customary, and reasonable (UCR) benchmark for a procedure in
the user's geography — the starting point for an estimate.

**How to query.**
- Inputs: CPT/HCPCS code + geographic area (ZIP-based) + (optional) modifier.
- Returns a percentile distribution of charges/allowed amounts for that procedure + area.

**ZIP precision — BAA-gated (applies to V1-Lite and Full V1).**
- **Without a FAIR Health BAA:** query at **3-digit ZIP** precision only (HIPAA Safe Harbor
  de-identification — a 3-digit ZIP is not individually identifying for permitted ranges).
- **With a BAA:** full 5-digit ZIP for tighter geographic accuracy.
- FAIR Health license/BAA procurement is a Brock parallel track; default to 3-digit ZIP
  until confirmed.

**Interpreting UCR.** Use a central percentile for the point estimate and the spread to
inform the confidence band (see `confidence_band_methodology.md`). State the percentile used.

**Edge cases.** Rare/variable procedures have wide distributions → widen the band and say so.

**Citation.** Tier A number with source: "FAIR Health UCR for [code] in [3-digit ZIP] is
~$X (Nth percentile) [FAIR Health, src_TBD]." Never present a UCR figure without naming FAIR
Health as the source.
