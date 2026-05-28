# qdrant_search_error_detection_rules

mode: universal

## What it does
Searches the `error_detection_rules` Qdrant collection for narrative billing-rule text (NCCI
policy reasoning, MUE narratives, modifier validity, ACA preventive, upcoding/phantom patterns).

## When to use
- To find the policy reasoning behind a suspected error and the language to cite when explaining it.

## When NOT to use
- For the structured bundling/units lookup (use `ncci_check_pair` / `mue_check` — the tabular
  truth lives in Postgres); for statutes (use `qdrant_search_laws_regulations`).

## Arguments
- `query` (string, required) — e.g. `"modifier 25 with same-day procedure"`.
- `applicable_codes` (array, optional) — e.g. `["99214","12031"]`.
- `effective_date` (date, optional, defaults to today for new questions).
- `max_results` (int, optional, default 10).

## Returns
```json
[{"rule_id":"modifier_25_em_with_procedure","rule_type":"modifier_validity",
  "narrative_text":"Modifier 25 indicates a significant, separately identifiable E/M …","score":0.9}]
```

## Errors and edge cases
- No match → `[]`. Pair the narrative with the structured `ncci_check_pair`/`mue_check` result
  for a definitive finding.
- PHI: queries should be about codes/rules, not patient identifiers; PreToolUse scrubs outbound
  args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Bill Detective.
