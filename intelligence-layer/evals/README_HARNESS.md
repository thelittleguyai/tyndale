# Eval Harness — Runbook & Handoff

This is the executable machinery for Tyndale's intelligence-layer evals. It proves
the pipeline end-to-end: load the known-answer golden set, validate it, compute
coverage, map coverage onto the seven ship gates, and (in live mode) run each case
through the actual agent and score it with an LLM judge.

For the corpus itself and its target counts, see [`golden/README.md`](golden/README.md).
For the adversarial synthetic generator, see [`synthetic/README.md`](synthetic/README.md).

## What's here

| File | Purpose |
|---|---|
| `run_golden_evals.py` | The runner. Offline (default) validates + reports; live scores against the agent + judge. |
| `golden/` | The known-answer cases, one JSON per case, all validating against `golden/schema.json`. |
| `synthetic/run_synthetic_generation.py` | Separate machine-generation of adversarial cases (unchanged; still a template with two `TODO(brock/eng)` blocks). |
| `../../.github/workflows/evals.yml` | CI gate: runs `run_golden_evals.py --offline` on PRs touching `intelligence-layer/**`. |

## Run it

### Offline (no deps, no network, no Postgres — this is what CI runs)

```bash
cd intelligence-layer/evals
python3 run_golden_evals.py --offline          # human report
python3 run_golden_evals.py --offline --json    # + machine-readable summary
```

Offline mode:
- discovers every `golden/**/*.json` (skips `schema.json` and `EXAMPLE.json`),
- schema-validates each with a **self-contained stdlib validator** (no `jsonschema`
  needed; if `jsonschema` happens to be installed it's used instead, same result),
- prints per-category / per-subcategory / per-difficulty counts,
- prints **ship-gate coverage** (which gates the seeded suite exercises),
- **exits non-zero if any case is schema-invalid** — the CI gate.

Offline mode reports **schema validity + coverage only**. It does not produce
gate pass/fail against thresholds — that needs live scored runs.

### Live (agent + LLM judge — scored ship-gate results)

Guarded so it can never fire by accident:

```bash
export TYNDALE_EVALS_LIVE=1
export ANTHROPIC_API_KEY=...            # the LLM judge (Opus 4.7)
# optional: export TYNDALE_JUDGE_MODEL=claude-opus-4-7
cd intelligence-layer/evals
python3 run_golden_evals.py --live
```

Live mode, per case: `run_target_system(case)` → candidate output →
`call_judge_model(...)` scores it against the case's `expected_output_traits` →
`score_output(...)` maps the judge's rubric onto per-ship-gate pass/fail →
aggregated into a pass-rate per gate.

The `anthropic` client is imported **lazily**, so offline mode needs nothing installed.

## Ship-gate mapping

The developer spec (D21 / build-plan Phase 6) locks seven ship gates. How the runner relates to each:

| # | Ship gate | Threshold | How the harness covers it |
|---|---|---|---|
| 1 | Citation faithfulness | ≥ 99.5% | Judge rubric #1 + cases carrying `required_citations` (Tier B, bill/negotiation). Offline: coverage only. |
| 2 | Hallucination rate | ≤ 1.0% | Judge rubric #2 + `should_not_contain` fabrication traps. Offline: coverage only. |
| 3 | Factual accuracy (Tier A) | ≥ 99% | Judge rubric #2/#4 on cases with `factual_assertions`. Offline: coverage only. |
| 4 | Refusal correctness | ≥ 98% | Judge rubric #3 on the `refusal_correctness` set (5 out-of-scope categories + in-scope controls). Offline: coverage only. |
| 5 | Voice-tier compliance | composite mean ≥ 4.0/5, no item < 3.0 | Judge rubric #4 on `tier_a/b/c` + `confident_voice_rubric`. Offline: coverage only. |
| 6 | Latency | p50 < 8s, p95 < 25s | **Not measurable from static cases.** Measured at runtime, out of this harness. |
| 7 | Judge calibration | Cohen's κ ≥ 0.6 vs. human | **Not measurable offline.** Requires human-labeled golden set + judge run, then κ. |

Offline mode marks gates 6 and 7 `not offline-measurable`.

## What's seeded (this bootstrap)

A **starter** known-answer set of **39 cases** (author `synthetic_opus47`), authored
from the skills' own diagnostic indexes/taxonomies and the reference voice-tier +
refusal docs, spread as:

- **bill_error_detection (7)** + **bill_detective subagent (2)** — bundling, upcoding,
  duplicate, preventive cost-share, NSA ER balance bill, payer-side deductible
  misapplied, encounter-verification phantom charge, MUE over-units, modifier-59 unbundle.
- **cost_estimation (3)** — exact-number-pressure → confidence band, fair-price check, deductible-met estimate.
- **coverage_connection_fhir (3)** — graceful degradation (bill-only), low-confidence manual extraction, multi-plan COB.
- **negotiation_strategy diagnostic (3)** — ERISA, NSA, charity-care framework selection (scripted action, not a drafted letter).
- **math_person (2)** — three-number independent audit (partial deductible; OOP-max met).
- **lead_planner (2)** — thinking-loop no-re-ask; session-open lead-with-status.
- **voice/safety (17)**: tier_a_factual (3), tier_b_legal (3, incl. an OMIT-uncited-claim adversarial), tier_c_strategic (1), confident_voice_rubric (1, three-tier composed), **refusal_correctness (9)**: **3 crisis/self-harm that MUST be declined with NO routing**, plus one each for clinical / legal-beyond-billing / financial / state-procedural, and **2 in-scope controls that must NOT be declined**.

Every seeded case validates against `golden/schema.json`. Confirm anytime with
`python3 run_golden_evals.py --offline` (expect: 39 discovered, 39 valid, exit 0).

The deferred Full-V1 skills/subagents (document_generation, charity_care_eligibility,
find_a_doctor, plan_a_visit; strategist, legal_researcher, code_validator) keep empty
`.gitkeep` placeholder dirs — intentionally unseeded until Full V1.

## Open scope decisions for Brock (the original `TODO(brock/eng)` items)

The machinery is proven; these are the judgment calls that turn the skeleton into the shipping suite:

1. **Target corpus size / scenario-mix weights.** The golden README targets ~200–400
   for V1-Lite (of a ~400–600 full target). This bootstrap seeds 39. Brock decides the
   per-skill and per-gate case budget and how heavily to weight the high-risk buckets
   (payer-side independent audit; crisis-decline). The synthetic generator's per-taxonomy
   targets (`synthetic/README.md`, ~2,250 total) are the adversarial backfill lever.
2. **Judge-rubric sign-off.** `JUDGE_SYSTEM_PROMPT` in `run_golden_evals.py` is a scaffold.
   Brock signs off the rubric text, the per-gate pass thresholds, and the 1–5 scoring anchors,
   then calibrates the judge against a human-labeled subset until **Cohen's κ ≥ 0.6** before
   the judge is trusted for gating.
3. **Live integration seams.** Two functions are the wiring points, both raising a clear
   `NotImplementedError` until done:
   - `run_target_system(case)` — call the runtime intelligence layer (Lead Planner / Skill
     dispatch) and return the user-facing text for a case's input.
   - `call_judge_model(...)` — currently a direct Anthropic call; point it at the runtime's
     hardened LiteLLM proxy if in-cluster spend logging is wanted (mirror
     `synthetic/run_synthetic_generation.py`'s `build_client()`).
4. **Reviewer discipline.** Golden README requires a second author to review each case
   before merge, and baseline updates require a second approver (D21). Seeded cases are
   authored `synthetic_opus47` and are **unreviewed** — treat as candidates pending Brock/
   attorney/billing-advocate review, not signed golden.

## Assumptions baked into the runner (change if wrong)

- Offline validator implements the JSON-Schema draft-07 subset `golden/schema.json` uses
  (type, required, enum, pattern, format:date, properties, items, additionalProperties). If
  the schema grows past that subset, extend `_validate_against_schema` or rely on the
  auto-detected `jsonschema` fallback (`USE_JSONSCHEMA_IF_AVAILABLE`).
- A ship gate "has coverage" if ≥1 golden case in one of its mapped `categories` exists.
  Gate categories are declared in `SHIP_GATES` in `run_golden_evals.py`.
- The offline stub judge (`stub_judge`) returns all-pass with a `STUB` marker purely so the
  scoring/report path runs without a model; it never counts toward a real gate result.
