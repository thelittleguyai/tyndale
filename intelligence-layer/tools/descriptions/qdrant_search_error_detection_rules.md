# qdrant_search_error_detection_rules

mode: universal

## What it does
Searches the `error_detection_rules` Qdrant collection for narrative billing-rule text — BOTH
provider-coding rules (NCCI policy reasoning, MUE narratives, modifier validity,
upcoding/phantom patterns) AND payer-side adjudication rules (deductible misapplication,
OOP-max ignored, network status misapplied, wrong coinsurance rate, auth-on-file ignored,
allowed amount above contract, COB misordering — 2026-08-22 extension). Payer-side rules
carry NO applicable_codes: they match on the adjudication facts in your query (EOB math,
accumulator positions, network status), so describe the discrepancy, not a code.

## When to use
- To find the policy reasoning behind a suspected error and the language to cite when explaining it.

## When NOT to use
- For the structured bundling/units lookup (use `ncci_check_pair` / `mue_check` — the tabular
  truth lives in Postgres); for statutes (use `qdrant_search_laws_regulations`).

## Arguments
- `query` (string, required) — e.g. `"modifier 25 with same-day procedure"`.
- `applicable_codes` (array, optional) — e.g. `["99214","12031"]`. Code filters only make
  sense for provider-coding rules; payer-side rules have none and are found semantically.
- `filters` (object, optional) — e.g. `{"rule_class": "payer_adjudication"}` to scope by
  class, or `{"responsible_party": "payer"}`.
- `effective_date` (date, optional, defaults to today for new questions).
- `max_results` (int, optional, default 10).

## Returns
```json
[{"rule_id":"modifier_25_em_with_procedure","rule_type":"modifier_validity",
  "rule_class":"provider_coding","responsible_party":"provider",
  "narrative_text":"Modifier 25 indicates a significant, separately identifiable E/M …","score":0.9},
 {"rule_id":"payer_deductible_misapplication_v1","rule_type":"deductible_misapplication",
  "rule_class":"payer_adjudication","responsible_party":"payer",
  "narrative_text":"When the EOB applies a deductible after the accumulated deductible is met …","score":0.87}]
```
When a finding rests on one of these rules, carry the rule's `responsible_party` into the
finding's facts (`facts.responsible_party`) so the card attributes it correctly.

## Errors and edge cases
- No match → `[]`. Pair the narrative with the structured `ncci_check_pair`/`mue_check` result
  for a definitive finding.
- PHI: queries should be about codes/rules, not patient identifiers; PreToolUse scrubs outbound
  args per BAA status (`docs/integration-contracts.md` §2.1).

## Used by
Bill Detective.
