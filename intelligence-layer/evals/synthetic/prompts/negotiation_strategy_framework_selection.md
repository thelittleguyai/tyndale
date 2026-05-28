# Synthetic Generation Prompt — Negotiation & Strategy diagnostic (framework selection)

## What this generates
Adversarial cases testing whether the V1-Lite Lead Planner picks the RIGHT appeal/negotiation
framework from the diagnostic (ERISA vs. ACA vs. NSA vs. DOI vs. charity vs. collections), and
recommends a scripted action — NOT a drafted letter.

## Target case count
150 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: picking the wrong framework, offering a menu of options instead of one
recommendation (P5 violation), or drafting a letter (deferred in V1-Lite). Pressure form:
ambiguous plan facts (self-funded vs. fully-insured, ER vs. chosen provider, in/after internal
appeal).
Tyndale's correct behavior: run the Negotiation & Strategy diagnostic to identify the single
applicable framework, then recommend a SPECIFIC scripted action (a phone-call script or a letter
the user sends themselves) per P5, set the deadline, and surface what's next (P2). Tier C voice,
no outcome prediction.
A failure looks like: wrong framework; "you could do X, Y, or Z" menu; drafting a letter for the
user; predicting the appeal will succeed.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "negotiation_strategy".

For each case:
1. Construct a realistic user_message with plan facts that point to one framework.
2. Include relevant user_profile (plan type self-funded/fully-insured/Medicare/Medicaid, state).
3. Include case_file_state (a confirmed finding to act on).
4. Define expected_output_traits — SHOULD name the correct framework + a specific scripted action
   + a deadline; MUST NOT dump options, draft a letter, or predict the outcome.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary plan type and the correct framework, state, surface form, context depth.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
V1-Lite ships the diagnostic ONLY — the correct output is a scripted action, never a drafted
letter (letter generation is Full V1). Weight cases on the scripted-action discriminator.
