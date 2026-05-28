# qdrant_search_laws_regulations

mode: universal

## What it does
Searches the `laws_regulations` Qdrant collection (ERISA, ACA, NSA, MHPAEA, IRS §501(r), EMTALA,
state law) for the statute/regulation chunks that ground a legal claim.

## When to use
- When a finding rests on a legal protection and you need the authority to cite (Tier B).

## When NOT to use
- For payer-specific medical-necessity policy (use `qdrant_search_payer_policies`); for general
  billing rules (use `qdrant_search_error_detection_rules`).

## Arguments
- `query` (string, required) — e.g. `"ERISA internal appeal deadline"`.
- `effective_date` (date, **REQUIRED**) — the date of service, e.g. `"2026-03-14"`. **The
  PreToolUse hook BLOCKS any query missing `effective_date`** (point-in-time correctness — see
  `docs/integration-contracts.md` §2.1, rule 3).
- `jurisdiction` (string, optional) — `federal` | `state_<XX>`.
- `max_results` (int, optional, default 10).

## Returns
```json
[{"chunk_id":"erisa_503_appeal_window","statute":"29 C.F.R.","section":"2560.503-1(h)",
  "chunk_text":"A group health plan's claims procedure must give a claimant at least 180 days …",
  "effective_date_start":"2002-01-01","effective_date_end":null,"score":0.94}]
```

## Errors and edge cases
- Missing `effective_date` → **blocked by PreToolUse** with a reason; supply the date of service.
- No match within the effective-date window → `[]`; do not assert a legal claim without a
  retrieved source (Grounding Doctrine — omit the claim).

## Used by
Lead Planner (V1-Lite — folded-in legal research). (Legal Researcher in Full V1.)
