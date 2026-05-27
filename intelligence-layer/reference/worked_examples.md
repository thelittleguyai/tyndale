# Worked Examples — Wrong vs Right Agent Behavior

This file accumulates concrete examples of wrong-vs-right agent behavior. It complements the
eval suite: evals test behavior, worked examples teach it in-context. When a mistake is caught
(via the feedback loop or human review), the corrected behavior is added here so the agent
doesn't repeat it.

## How this file is loaded

The behavioral core (behavioral_core.md) references this file. The runtime injects entries
most-relevant-first as the context budget allows. Highest priority entries: mistakes recently
caught in production; recurring categories of confusion; high-stakes paths (legal claims,
payer-side findings).

## Entry format

### {Short title}

**Situation.** {Brief context — what was happening when the mistake occurred or might occur.}

**Wrong behavior.** {What the agent did, or might do, that violates the behavioral core or a
doctrine.}

**Correct behavior.** {What the agent should do.}

**Why.** {One-sentence reasoning anchored in the relevant principle, doctrine, or rule.}

**Date added.** {YYYY-MM-DD}

**Source.** {feedback_event_id | manual_review | seed_example}

---

## Examples

(Empty at V1-Lite Phase 1A. Seed examples will be added later in the build per the Phase 5
plan. Feedback-loop triage will append entries automatically once the feedback pipeline is
live.)
