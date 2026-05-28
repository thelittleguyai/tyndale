# Synthetic Generation Prompt — Lead Planner (proactive thinking-loop application)

## What this generates
Adversarial cases testing whether the Lead Planner runs the enumerated seven-question thinking
loop before responding — anticipating (P1), surfacing what's next (P2), bundling questions (P3),
maximizing action per turn (P4), and defaulting to a recommendation (P5).

## Target case count
200 cases (default).

## Generation prompt for Opus 4.7
```
You are generating adversarial eval cases for Tyndale, an AI-powered medical billing
reconciliation platform. Each case must surface a specific failure mode in Tyndale's
intelligence layer.

Failure mode targeted: skipping the proactive thinking loop — asking the user for something
already in the case file (P1), stopping at "done" without surfacing the next step or a deadline
(P2), interrogating with sequential questions (P3), doing only the literal task (P4), or dumping
options (P5).
Tyndale's correct behavior: run the seven-question loop (what do I know / what's missing / what
hasn't the user asked / deadlines / specific next action — in V1-Lite a SCRIPTED action, not a
drafted letter / grounding source / single most important thing), then lead with the answer,
attach grounding, surface the next step, and ask only the one trivial question that unlocks the
most (bundled).
A failure looks like: re-asking known info; no surfaced next step/deadline; multi-question
interrogation; minimal literal response; option menu.

Generate <N> cases. Each case MUST match intelligence-layer/evals/golden/schema.json with
`category` = "lead_planner".

For each case:
1. Construct a realistic user_message; often put the "missing" answer in case_file_state to test P1.
2. Include relevant user_profile.
3. Include case_file_state (sometimes already containing what a lazy agent would re-ask).
4. Define expected_output_traits — SHOULD infer from case state, surface next step + deadline,
   bundle any genuine question; MUST NOT re-ask known info, stop without next steps, or dump options.
5. Provide expert_reasoning.
6. Set difficulty to "adversarial".
7. Set author to "synthetic_opus47".

Diversity: vary which principle is under pressure, plan/state/demographics, surface form, context depth.
Anti-requirements: no near-duplicates; synthetic names + glossary payers; no copyrighted text.

Output a JSON array, one object per case, each matching schema.json.
```

## V1-Lite note
Use the V1-Lite collapsed Lead Planner: question 5 ("specific next action") means a scripted
phone call/letter the user makes — never a drafted letter. Include session-open lead-with-status
cases (returning user with open cases) where appropriate.
