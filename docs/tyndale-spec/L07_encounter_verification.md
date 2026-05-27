# Task L07 — Encounter verification flow (did the service actually happen?)

**Phase:** L2 · V1-Lite new
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** L01–L06, plus full Build Kit Task 08 (Bill Error Detection Skill, which now contains the 06_encounter_verification reference files)

> **Why this task exists.** A bill can be coded for a service, a
> complexity level, or an item the patient never received — phantom
> charges, upcoded visit levels, billed-but-not-performed tests. In full
> Tyndale, this is verified against clinical encounter data (from
> 1upHealth or another vendor). In V1-Lite that data isn't available, so
> the USER is the verification source. But a user can't evaluate "CPT
> 99285" — so Tyndale must translate each charge into plain language the
> user can confirm against their lived experience of the visit. This is
> half of Tyndale's audit (the other half, the math audit, lives in Math
> Person). See the Independent Audit Doctrine in reference/principles.md.

## What this task does

Wires the encounter-verification capability into V1-Lite: the line-item
plain-language translation, the user-confirmation flow, and the
conversion of a mismatch into a candidate finding. The reference content
lives in the Bill Error Detection Skill (built in Task 08); this task
makes sure the V1-Lite Lead Planner and web app actually USE it, and adds
the V1-Lite-specific consent/forward-compat notes.

## Prompt to paste into Claude Code

```
Wire encounter verification into V1-Lite. The Skill content already
exists at skills/bill_error_detection/06_encounter_verification/
(lineitem_plain_language.md and user_confirmation_flow.md). This task
connects it to the V1-Lite flow.

First read:
- skills/bill_error_detection/00_diagnostic_index.md (checks 0a, 0b)
- skills/bill_error_detection/06_encounter_verification/lineitem_plain_language.md
- skills/bill_error_detection/06_encounter_verification/user_confirmation_flow.md
- subagents/lead_planner/v1_lite/system_prompt.md (the collapsed Lead Planner)
- reference/principles.md (the Independent Audit Doctrine + P1, P3)
- reference/refusals.md (the clinical-judgment line)

Then do the following:

1. Add an "Encounter verification (V1-Lite)" section to the collapsed
   Lead Planner prompt (subagents/lead_planner/v1_lite/system_prompt.md):

   - When a bill/EOB is being analyzed, after extraction and BEFORE
     finalizing findings, run encounter verification: translate each
     charged line item to plain language (per lineitem_plain_language.md)
     and ask the user to confirm it matches their visit.
   - Bundle the confirmations per P3 — present the translated line items
     as ONE checklist-style message ("Here's what you were billed for, in
     plain terms — does each of these match what actually happened?"), not
     a sequence of separate questions.
   - HARD LINE (per refusals.md): ask the user to confirm FACTS about
     their visit ("Were you in the ER for a long time with a complex
     situation?" / "Did you actually receive this lab test?"), NEVER a
     clinical judgment ("Was this medically necessary?" / "Should you have
     gotten this?"). The user verifies WHAT HAPPENED, not whether it
     should have.
   - A mismatch ("I was only there 20 minutes" against a billed
     high-complexity visit; "I never got that test") becomes a candidate
     finding: phantom charge or upcoding. Route it through the Bill Error
     Detection diagnostic (checks 0a/0b → 01_provider_billing/upcoding.md
     or phantom_charges.md) for confirmation against the rules.
   - Tone: this is not an interrogation. Frame it as Tyndale double-
     checking on the user's behalf — "Insurers and billing systems make
     mistakes, so I want to make sure you were actually billed for what
     you got."

2. Add a brief "Encounter verification" note to the web app scaffold
   plan (this will inform Task L08): the chat-anchored results flow needs
   a lightweight, scannable confirmation UI — each translated line item
   with a one-tap "yes, that's right" / "no, that's not what happened" /
   "not sure". The "not sure" option matters — it must not force a false
   confirmation. Capture these confirmations as feedback events (they're
   high-value labels — see below).

3. Forward-compatibility note — add to the V1-Lite handoff (Task L09)
   and to user_confirmation_flow.md:
   - In full Tyndale, clinical encounter data (1upHealth or another
     vendor) verifies what happened automatically, reducing reliance on
     user confirmation.
   - BUT the user-confirmation flow does NOT get thrown away — it remains
     (a) the fallback when clinical data is unavailable or incomplete, and
     (b) a cross-check against the clinical data itself.
   - CRITICAL DATA VALUE: every V1-Lite user confirmation ("this line
     item matched / didn't match my visit") is a LABEL. When clinical
     encounter data arrives in full Tyndale, these labels are the
     validation set that proves the automated encounter-verification works.
     So V1-Lite isn't just shipping a fallback — it's generating the
     training/validation data that makes the full version's automated
     verification trustworthy. Wire these confirmations into the feedback
     loop (feedback/capture_schema.json) with a feedback_type of
     "value_confirmation" and a field indicating it's an encounter
     confirmation.

4. Update feedback/capture_schema.json to ensure the value_confirmation
   object can represent an encounter confirmation (add an optional
   "confirmation_kind" field with values "extracted_value" |
   "encounter_lineitem", and for encounter confirmations capture: the
   line item code, the plain-language translation shown, and the user's
   response yes/no/unsure).

Commit with message "Wire encounter verification into V1-Lite flow".
```

## Done when

- The collapsed Lead Planner prompt has an encounter-verification section with the facts-not-clinical-judgment line explicit
- The confirmation flow bundles per P3 and offers a "not sure" option
- The forward-compatibility + data-value note is recorded
- `feedback/capture_schema.json` can represent encounter confirmations
- Git log shows the commit

## Next task

[Task L08 — Mobile-friendly web app shell](L08_web_app_shell.md)
