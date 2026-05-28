# Synthetic Adversarial Cases

Opus 4.7 generates adversarial eval cases against 12 failure-mode taxonomies, one per
prompt file in [`prompts/`](prompts/). Every generated case matches the golden-example
schema ([`../golden/schema.json`](../golden/schema.json)), so synthetic cases slot into
the exact same Braintrust eval runner the hand-authored golden examples use — they are
the same format, just machine-generated and adversarial rather than expert-authored.

The runner is [`run_synthetic_generation.py`](run_synthetic_generation.py). It does **not**
execute in Phase 2E (no Anthropic key in this environment, and two `TODO(brock/eng)`
blocks remain). `--help`, `--list`, and `--dry-run` work today with zero dependencies.

## Taxonomies & V1-Lite targets

Each taxonomy is a prompt-file stem and a `cases/<taxonomy>/` output bucket. Several
prompts deliberately share one schema `category` (3× `bill_error_detection`, 2×
`coverage_connection_fhir`) but stay in separate buckets so each failure mode can be
spot-checked and re-run independently.

| Taxonomy (prompt file) | schema `category` | `subcategory` | Target | Generated | Spot-checked |
|---|---|---|---|---|---|
| bill_error_detection_provider_side | bill_error_detection | provider_side | 250 | 0 | 0 |
| bill_error_detection_payer_side | bill_error_detection | payer_side | 250 | 0 | 0 |
| bill_error_detection_encounter_verification | bill_error_detection | encounter_verification | 150 | 0 | 0 |
| cost_estimation_confidence_band | cost_estimation | — | 150 | 0 | 0 |
| coverage_connection_manual_extraction | coverage_connection_fhir | manual_extraction | 150 | 0 | 0 |
| coverage_connection_graceful_degradation | coverage_connection_fhir | graceful_degradation | 150 | 0 | 0 |
| negotiation_strategy_framework_selection | negotiation_strategy | — | 150 | 0 | 0 |
| lead_planner_thinking_loop | lead_planner | — | 200 | 0 | 0 |
| math_person_three_number_audit | math_person | — | 200 | 0 | 0 |
| voice_tier_a_factual | tier_a_factual | — | 150 | 0 | 0 |
| voice_tier_b_legal_citation | tier_b_legal | — | 200 | 0 | 0 |
| refusal_correctness | refusal_correctness | (5 out-of-scope) | 250 | 0 | 0 |
| **TOTAL** | | | **~2,250** | **0** | **0** |

V1-Lite ships a subset of the full eval ambition (~200–400 examples per the golden README);
these synthetic cases backfill adversarial coverage where hand-authored golden examples are
still thin. The Phase 4 feedback loop grows the real suite from production cases post-launch.

## How to run (once API access lands — Phase 2D)

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Credentials — Anthropic API directly, OR the runtime's LiteLLM proxy
export ANTHROPIC_API_KEY=your_key_here
export ANTHROPIC_BUDGET_LIMIT_USD=100       # hard cap; default 30 covers a single taxonomy,
                                            # raise it (e.g. 100) before running --all

# 3. Inspect without spending anything
python run_synthetic_generation.py --list
python run_synthetic_generation.py --taxonomy refusal_correctness --dry-run

# 4. Generate one taxonomy, then all of them
python run_synthetic_generation.py --taxonomy refusal_correctness
python run_synthetic_generation.py --all
```

The runner extracts the `## Generation prompt for Opus 4.7` block from each prompt file,
substitutes the batch size for `<N>`, calls Opus 4.7 in batches of 25, validates each
returned case against `schema.json` (and checks it carries the taxonomy's expected
`category`), and writes survivors to `cases/<taxonomy>/<case_id>.json`.

### Before a live run — fill the two TODO blocks

1. **`build_client()`** — wire the Anthropic client or the runtime LiteLLM proxy (Phase 2D).
2. **`spot_check()`** — the 10% manual-review workflow described below.

## Cost expectations

The Phase 2E spec quoted **~$10–25** for the full set; treat that as an optimistic floor.
Output tokens dominate (each case is a full JSON record, not a snippet), and at Opus 4.7
output rates a ~2,250-case run lands closer to **~$60–100** — the runner's own placeholder
per-token math estimates ≈ $85 (visible in any `--dry-run`). Reconcile before spending:

- **The per-token rates in `run_synthetic_generation.py` are placeholders — confirm
  against live Opus 4.7 pricing before the first full run.**
- Prompt caching on the shared meta-prompt trims *input* cost only; it does not reduce the
  output cost that dominates here.
- The runner runs a pre-flight estimate and **aborts if projected spend exceeds
  `ANTHROPIC_BUDGET_LIMIT_USD`** (default $30 — permits any single taxonomy, ≈ $10, but
  intentionally blocks `--all` until you raise the cap).
- Generate one taxonomy at a time to keep spend incremental and reviewable.

## Spot-check workflow (10% before promotion)

Synthetic cases are **not** promoted to the active Braintrust suite until reviewed. After a
taxonomy generates, sample ~10% of its cases:

```bash
ls cases/<taxonomy>/ | sort -R | head -n 20
```

For each sampled case confirm:

- it targets the intended failure mode (no scope creep);
- `expected_output_traits` are concrete and an LLM judge can actually evaluate them;
- it is not a near-duplicate of another case (cosmetic-only variation);
- no real PII and no copyrighted payer-policy text leaked in (synthetic names + glossary
  payers only).

Record pass/fail in the table above. If quality is inconsistent, revise the prompt in
`prompts/<taxonomy>.md` and re-run that taxonomy.

## When to re-run

- A failure-mode taxonomy expands or a new one is added.
- A prompt template in `prompts/` changes materially.
- After a major Skill or subagent system-prompt revision (the behavior under test moved).
- After a `schema.json` change that affects required fields or the `category` enum.

## How these get used

1. Run `run_synthetic_generation.py` against each prompt (Phase 2D / Phase 6).
2. Spot-check 10% per taxonomy; revise + re-run if quality is uneven.
3. Promote accepted cases into the Braintrust eval suite.
4. Per-PR smoke evals sample from this set; nightly evals run the full set.

## Forward compatibility

Synthetic cases are byte-for-byte the same JSON shape as golden examples — both validate
against `../golden/schema.json` — so no separate loader, judge, or scoring path is needed.
The only distinguishing field is `author: "synthetic_opus47"` (vs. `brock` /
`contracted_attorney` / `billing_advocate` for hand-authored golden cases), which lets the
suite weight or filter by provenance if desired.
