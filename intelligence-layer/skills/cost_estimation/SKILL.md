---
name: cost_estimation
description: |
  Estimate what a procedure SHOULD cost — and what the user will actually owe —
  using FAIR Health UCR (geographic- and procedure-specific), the user's plan
  benefits (deductible state, coinsurance, OOP max), and Medicare RVU rates as a
  sanity-check benchmark. Returns a confident RANGE with reasoning and named
  sources, never a bare guess. Use this when the user asks "what will this cost?",
  "is this a fair price?", or wants a pre-service estimate. Do NOT use it to find
  errors on a bill that already exists (use bill_error_detection), to pull/parse
  coverage data (use coverage_connection_fhir), or to sequence an appeal (use
  negotiation_strategy).
version: 1.0.0
---

# Cost Estimation Skill

The playbook for estimating procedure cost and expected member responsibility.

## Methodology

1. Start with **FAIR Health UCR** for the procedure + geography (the usual, customary,
   and reasonable benchmark).
2. Apply the user's **plan benefits** — deductible state (met / partial / unmet),
   coinsurance, and out-of-pocket maximum — to turn the UCR/allowed amount into expected
   member responsibility.
3. Cross-reference **Medicare RVU** allowable rates as a sanity check on the UCR figure.

## Foundation references

- [`intelligence-layer/reference/principles.md`](../../reference/principles.md) — anticipate, surface what's next.
- [`intelligence-layer/reference/voice_tiering.md`](../../reference/voice_tiering.md) — numbers are Tier A; the estimate framing is Tier C (reasoning, never an outcome promise).
- [`intelligence-layer/reference/citations.md`](../../reference/citations.md) — cite the source data.

## HARD RULES

1. **Every estimate is a confidence band, never a point estimate.** The user sees
   "expected range **$1,800–$2,400**", not "expected $2,100". See
   `reference/confidence_band_methodology.md`.
2. **Every estimate cites its source data** — FAIR Health for UCR, Medicare for the
   benchmark, and the user's plan documents for benefits. No unsourced numbers (this is the
   Grounding Doctrine applied to pricing).

## Reference files

- `reference/fair_health_lookup.md` — querying FAIR Health UCR; 3-digit-ZIP fallback without a BAA
- `reference/medicare_rvu_lookup.md` — Medicare allowable as a benchmark
- `reference/plan_benefit_application.md` — applying the user's benefits to a raw UCR estimate
- `reference/deductible_state_handling.md` — unmet / partially-met / fully-met deductible
- `reference/coinsurance_oop_calculation.md` — coinsurance % and OOP-max application
- `reference/confidence_band_methodology.md` — constructing the ± range
- `reference/edge_cases.md` — multiple coverage, COB, mid-year changes, pre/post-deductible
