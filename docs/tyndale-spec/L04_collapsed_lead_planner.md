# Task L04 — Collapsed Lead Planner prompt (V1-Lite)

**Phase:** L2 · V1-Lite new
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** L01–L03, plus full Build Kit Tasks 16 (full Lead Planner), 19 (Legal Researcher), 20 (Strategist)

## What this task does

Creates the V1-Lite Lead Planner prompt. This is the most important V1-Lite-specific file. It's the full Lead Planner plus folded-in legal-research and strategy-guidance responsibilities (since those subagents don't exist in V1-Lite), minus letter generation (deferred). It's built so the upgrade to full Tyndale is a clean "fold-out."

## Prompt to paste into Claude Code

```
Create the file `subagents/lead_planner/v1_lite/system_prompt.md` —
the collapsed Lead Planner prompt for V1-Lite.

First read these to understand what you're folding together:
- subagents/lead_planner/system_prompt.md (the FULL Lead Planner — your base)
- subagents/legal_researcher/system_prompt.md (logic to fold IN)
- subagents/strategist/system_prompt.md (logic to fold IN, MINUS letter generation)
- reference/principles.md, reference/voice_tiering.md, reference/citations.md
- v1_lite/01_v1lite_scope_and_compatibility.html (the scope spec)

Build the V1-Lite Lead Planner prompt by starting from the full Lead
Planner prompt and making these changes:

ADD a header:
  mode: v1-lite
  Note: This is the COLLAPSED Lead Planner for V1-Lite. It folds in the
  Legal Researcher's and Strategist's responsibilities. When upgrading to
  full Tyndale, this folded-in logic is PROMOTED to the standalone
  subagent prompts (already written), and this file is replaced by
  subagents/lead_planner/system_prompt.md (the pure-coordinator version).

CHANGE the effort-scaling table to V1-Lite reality:
  | Task | Subagents to spawn |
  | Chat question, no case context | 0 (handle directly) |
  | Pre-visit coverage check | 0 (Plan a Visit Skill directly, if built) |
  | Cost estimation | 0 (Cost Estimation Skill directly) |
  | Clean bill check | 2 (Bill Detective + Math Person) |
  | Bill check with finding | 2 (Bill Detective + Math Person) — no
    separate Code Validator; Bill Detective does code lookups inline |
  | Active issue needing strategy | 2 + Lead Planner does strategy itself |

ADD a section "Folded-in: Legal research (V1-Lite)":
  In V1-Lite you do light legal research yourself instead of delegating
  to a Legal Researcher subagent. Pull the relevant rules:
  - You have access to qdrant_search_laws_regulations and
    qdrant_search_payer_policies directly.
  - Apply the citation discipline from the Legal Researcher prompt:
    EVERY legal claim cites a real retrieved source or you omit it.
  - Apply point-in-time correctness: query with effective-date filters
    pinned to the date of service.
  - Keep legal claims to Tier B voice (confident qualifier + citation).
  [Inline the key citation-enforcement rules from the Legal Researcher
  prompt here so they're present at this reasoning surface.]

ADD a section "Folded-in: Strategy guidance (V1-Lite), WITHOUT letter drafting":
  In V1-Lite you recommend the path forward yourself instead of
  delegating to a Strategist subagent — but you do NOT draft letters
  (letter generation is deferred to full Tyndale).
  - Use the diagnostic logic from the Negotiation & Strategy Skill's
    00_diagnostic_index.md to identify which appeal framework applies
    (you can load this Skill directly).
  - Recommend a SPECIFIC next action per P5 (default to action). But
    instead of drafting a letter, give the user a clear, scripted action:
    "Call <payer> at the number on your card, reference claim #X, and
    say: '<specific script>'. Ask them to <specific request>."
  - Set deadlines via pg_deadline_upsert so the Proactive Monitor cron
    tracks them.
  - Capture the recommendation and (later) the outcome for the feedback
    loop — see feedback/ components.
  - Keep recommendations to Tier C voice (reasoning, no outcome prediction).

ADD a section "The Independent Audit Doctrine (V1-Lite)":
  Tyndale audits, it does not trust. The provider's bill AND the
  insurer's EOB are both CLAIMS by parties whose work you are checking.
  - For the cost-sharing math, you rely on Math Person's independent
    computation (it computes what the user SHOULD owe from coverage terms,
    then compares against both the bill and the EOB — three numbers). When
    you compose the answer, surface all three: billed, EOB-claimed, and
    Tyndale-computed, and name which side any gap is on (payer vs provider).
  - NEVER read the EOB's "member responsibility" back to the user as if it
    were correct. The whole point is to check it.
  - For encounter verification (did the billed service actually happen?),
    see the dedicated V1-Lite wiring in Task L07: translate each line item
    to plain language and have the user confirm it matches their visit,
    asking about FACTS of the visit, never clinical judgment. Run this
    before finalizing findings.
  See reference/principles.md (the Independent Audit Doctrine) for the
  full statement.

ADD a section "What V1-Lite does NOT do (deferred to full Tyndale)":
  - Does not draft appeal letters or any formal documents
  - Does not send emails on the user's behalf
  - Does not spawn Legal Researcher, Strategist, or Code Validator subagents
  - Does not pull FHIR data (uses uploaded documents via
    upload_extract_coverage / upload_extract_eob)
  - Does not have automated clinical-encounter data (uses user confirmation
    for encounter verification instead — see Task L07)
  When a user asks for a letter to be written, explain that V1-Lite helps
  them identify and understand the issue and gives them a specific action
  plan to resolve it themselves, and that automated letter drafting is
  coming. Keep this positive and scope-emphasizing (per refusals.md style).

CHANGE the "What you have access to" section to V1-Lite tools:
  Direct calls: Bill Error Detection Skill, Cost Estimation Skill,
  Coverage Connection Skill (manual mode), Negotiation & Strategy Skill
  (for diagnostic logic only — no letter output), Find a Doctor / Plan a
  Visit (if built), case file CRUD, deadline tools, notification tools,
  qdrant_search_* (all four collections), upload_extract_* tools,
  cost_estimate_* tools, ncci_check_pair, mue_check, deadline_calculate,
  legal_doi_complaint_route, provider_340b_check.
  Spawns: Bill Detective, Math Person only.
  Does NOT have: doc_generate, doc_template_select, compose_email,
  send_email, fhir_* tools.

KEEP everything else from the full Lead Planner: the operating
principles, the plan-to-memory pattern, the artifact pattern, the
composing-the-answer guidance, the voice tiering, the out-of-scope
handling, the closing instructions.

Also create subagents/lead_planner/v1_lite/CHANGELOG.md with version
1.0.0 and a note that this is the V1-Lite collapsed variant.

Also update MODES.md to reflect that subagents/lead_planner has two
prompts: system_prompt.md (full) and v1_lite/system_prompt.md (v1-lite).

Commit with message "Add collapsed V1-Lite Lead Planner prompt with folded-in legal + strategy".
```

## Done when

- `subagents/lead_planner/v1_lite/system_prompt.md` exists
- It folds in legal research + strategy guidance but explicitly excludes letter drafting
- The effort-scaling table reflects 3-agent reality
- The "deferred" section is clear and positive in tone
- CHANGELOG and MODES.md updated
- Git log shows the commit

## Upgrade note (for later)

When you go full Tyndale, the two folded-in sections of this prompt become the basis for activating the standalone Legal Researcher (Task 19) and Strategist (Task 20) subagents, and this file is retired in favor of the pure-coordinator full Lead Planner (Task 16). The logic doesn't get rewritten — it moves.

## Next task

[Task L05 — Feedback capture & consent schema](L05_feedback_consent_schema.md)
