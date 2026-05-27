# Task 23 — Build the collection metadata schemas

**Phase:** 5 · Knowledge collection scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Phases 1-4 complete

## What this task does

Creates the JSON schemas defining the metadata fields for all four Qdrant knowledge collections. Engineers use these schemas when implementing the actual collection setup and the rerank instructions.

## Prompt to paste into Claude Code

```
Create the following files in `collections/schemas/`:

1. `billing_codes.json` — JSON schema for the billing_codes collection
2. `error_detection_rules.json` — JSON schema for error_detection_rules
3. `laws_regulations.json` — JSON schema for laws_regulations
4. `payer_policies.json` — JSON schema for payer_policies
5. `rerank_instructions.md` — the per-collection rerank instructions

For each JSON schema file, use JSON Schema (draft 07 or later) format
and document:
- Top-level type (object)
- Required fields
- Optional fields
- Type constraints per field
- Examples of valid values

The fields per collection are (from the developer spec):

billing_codes:
- code (string, required) — the CPT/HCPCS/ICD-10 code
- code_system (enum: "CPT" | "HCPCS" | "ICD-10", required)
- descriptor (string, required) — full code descriptor text
- category (string, required) — code category for filtering
- effective_year (integer, required)
- valid_modifiers (array of strings, optional) — modifiers valid with this code

error_detection_rules:
- rule_id (string, required)
- rule_type (string, required) — e.g., "ncci_ptp", "mue", "modifier_validity"
- applicable_codes (array of strings, required) — codes this rule applies to
- effective_date_start (date, required)
- effective_date_end (date, required, nullable for current rules)
- payer (string, nullable) — null for universal rules
- authority (string, required) — "CMS" | "<payer_name>" | "state_<XX>"
- narrative_text (string, required) — the policy text that gets embedded
- structured_rule_id (string, optional) — pointer to Postgres structured table
  for NCCI/MUE narrative rules

laws_regulations:
- chunk_id (string, required)
- jurisdiction (string, required) — "federal" | "state_<XX>"
- statute (string, required) — e.g., "29 U.S.C." or "Cal. Ins. Code"
- section (string, required)
- effective_date_start (date, required)
- effective_date_end (date, required, nullable for current law)
- document_type (enum: "statute" | "regulation" | "sub_regulatory_guidance")
- parent_title (string, optional)
- parent_part (string, optional)
- chunk_text (string, required) — the embedded text
- last_verified_date (date, required) — set by Regulation Researcher cron

payer_policies:
- chunk_id (string, required)
- payer (string, required)
- policy_id (string, required) — payer's internal policy identifier
- version (string, required)
- effective_date_start (date, required)
- effective_date_end (date, required, nullable)
- applicable_codes (array of strings, optional)
- plan_type (enum: "commercial" | "Medicare" | "Medicaid")
- chunk_text (string, required)
- last_verified_date (date, required)

For rerank_instructions.md, write the default rerank instructions per
collection (these are loaded by Qdrant at query time for instruction-
following reranking):

# Rerank Instructions

## laws_regulations
"Prefer statutory law over case law. Prefer federal authorities over
state when the question implicates ERISA preemption. Prefer current
law over superseded provisions. When multiple statutes apply, prefer
the more specific over the more general."

## payer_policies
"Return only policies effective on the date of service. De-prioritize
policies from the wrong plan year. Prefer payer-specific over generic
policy. Prefer specific code-level policy over general medical-necessity
policy when both exist."

## error_detection_rules
"Prefer NCCI edits over general billing guidance. Return rules specific
to the code combination, not parent category. Prefer payer-specific rules
when the query specifies a payer."

## billing_codes
"Prefer exact code matches over similar codes. Return the descriptor for
the queried code first. When searching by descriptor text, prefer codes
that match clinical specificity (e.g., laterality, anatomic location)."

For each .json file, include a small example of a valid record at the
bottom under an "Example" comment block.

Commit with message "Add collection metadata schemas and rerank instructions".
```

## Done when

- 4 JSON schema files exist in `collections/schemas/`
- `rerank_instructions.md` exists in the same directory
- Each schema validates with a JSON Schema validator
- Git log shows the commit

## Next task

[Task 24 — Build the ingestion script templates](24_ingestion_templates.md)
