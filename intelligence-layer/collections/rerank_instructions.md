# Rerank Instructions

Per-collection default instructions for instruction-following reranking (Voyage
`rerank-2.5`). These are the **defaults** loaded at query time; subagents can override
per query in Phase 2, and per-collection tuning against real query distributions is Phase 5.

Source: developer spec §7 ("Default rerank instructions"), mirrored in build-kit Task 23.

## laws_regulations
"Prefer statutory law over case law. Prefer federal authorities over state when the question implicates ERISA preemption. Prefer current law over superseded provisions. When multiple statutes apply, prefer the more specific over the more general."

## payer_policies
"Return only policies effective on the date of service. De-prioritize policies from the wrong plan year. Prefer payer-specific over generic policy. Prefer specific code-level policy over general medical-necessity policy when both exist."

## error_detection_rules
"Prefer NCCI edits over general billing guidance. Return rules specific to the code combination, not parent category. Prefer payer-specific rules when the query specifies a payer."

## billing_codes
"Prefer exact code matches over similar codes. Return the descriptor for the queried code first. When searching by descriptor text, prefer codes that match clinical specificity (e.g., laterality, anatomic location)."
