# Task 27 — Author the golden eval examples

**Phase:** 6 · Eval test data
**Who:** Brock (primary author) + Claude Code (drafting help) + contracted attorney + billing advocate
**Estimated time:** 30–60 hours spread across multiple sessions
**Depends on:** Task 26

## What this task does

This is the heaviest Brock-led task in the kit. Authoring ~400 golden eval examples is what makes the eval system actually useful. Claude Code helps draft examples for review, but the final expected_output_traits must be expert-validated.

## How this works

Unlike the other tasks, this one isn't a single paste-and-go prompt. It's a structured authoring workflow that runs over multiple sessions.

## Workflow

### Step 1 — Get drafts from Claude Code for the easy cases (Brock + Claude Code)

For Skills where the rules are well-defined (Bill Error Detection categories with clear NCCI rules; preventive coverage cases with clear ACA §2713 application), Claude Code can draft golden examples that Brock reviews and approves.

**Prompt for Claude Code (per category):**

```
I need golden eval examples for the `<category>` category. Per
evals/golden/schema.json, generate 5 candidate examples covering the
key scenarios:

[list the specific scenarios for this category]

For each example:
1. Write a realistic user_message
2. Define the expected_output_traits per the schema
3. Provide expert_reasoning explaining why the expected answer is correct
4. Set difficulty to easy/medium/hard
5. Set author to "brock" (you'll be reviewing them)

Reference reference/principles.md, reference/voice_tiering.md,
reference/citations.md, and the relevant Skill files to make sure
expected output traits are consistent with how Tyndale should actually
behave.

Output 5 JSON files matching schema.json. Save them to
evals/golden/<appropriate_directory>/.

When done, summarize what you generated and what additional examples
you'd recommend for full coverage.
```

After Claude Code generates the candidates, Brock reviews each one. Edit, accept, or reject. Commit accepted examples.

### Step 2 — Author the legal-interpretation examples with the contracted attorney

For Tier B legal interpretation examples (NSA violations, ERISA appeals, mental health parity, charity care), work with the contracted attorney. Brock or the attorney drafts; the other reviews.

**Suggested attorney engagement:**
- Hourly engagement, structured around: "I'll send you a scenario and the expected legal output. Tell me whether the legal claim is well-founded, what citation should support it, and whether the recommended next step is appropriate."
- Target: 100–150 attorney-reviewed legal-interpretation examples.

### Step 3 — Author bill-detection examples with the billing advocate

For Bill Error Detection examples, work with a contracted billing advocate. Brock drafts; advocate reviews.

- Target: 100–150 advocate-reviewed bill-detection examples.

### Step 4 — Author the voice and safety examples (Brock)

These are Brock-led. They test voice tier compliance, refusal correctness, and confident-voice rubric.

- Target: 50 voice and safety examples.

### Step 5 — Track progress

Maintain `evals/golden/PROGRESS.md` with running counts per category. When you hit the targets, commit a "Golden examples V1 complete" milestone.

## Initial paste-prompt for Claude Code to set up the progress tracker

```
Create evals/golden/PROGRESS.md with the following structure:

# Golden Examples — Progress Tracker

## V1 Targets

| Category | Target | Current | Notes |
|----------|--------|---------|-------|
| Bill Error Detection | 100 | 0 | Brock + billing advocate |
| Document Generation | 60 | 0 | Brock + attorney for legal claims |
| Negotiation & Strategy | 50 | 0 | Brock + attorney |
| Charity Care Eligibility | 30 | 0 | Brock |
| Cost Estimation | 20 | 0 | Brock |
| Coverage Connection & FHIR | 20 | 0 | Brock |
| Find a Doctor | 15 | 0 | Brock |
| Plan a Visit | 15 | 0 | Brock |
| Lead Planner | 30 | 0 | Brock |
| Subagent-specific (other 5) | 60 | 0 | Brock + relevant expert |
| Voice tier A | 15 | 0 | Brock |
| Voice tier B | 15 | 0 | Brock + attorney |
| Voice tier C | 15 | 0 | Brock |
| Refusal correctness (5 cats) | 25 | 0 | Brock (5 per category) |
| Confident voice rubric | 10 | 0 | Brock |
| **TOTAL** | **~480** | **0** | |

## Authoring sessions

Use this section to log each session:

### YYYY-MM-DD — <session description>
- Authored: <count>
- Categories: <which>
- Notes: <observations, gaps identified>

## Quality gates

- Every example reviewed by author + 1 reviewer before commit
- LLM judge calibrated against Brock's labels (Cohen's κ ≥ 0.6 target)

Commit with message "Add golden examples progress tracker".
```

## Done when

- `PROGRESS.md` exists
- The authoring workflow is underway (this task takes weeks to fully complete)
- At least 50 examples authored in any category that can be done before handoff to engineers (so engineers have something to test against)

## Notes

This task doesn't have a clean "done" — it's ongoing work that overlaps with the engineering build. The engineers can start work as soon as Tasks 30–32 are done; golden examples can be authored in parallel and the eval suite picks them up as they land.

## Next task

[Task 28 — Synthetic adversarial generation prompts](28_synthetic_generation_prompts.md)
