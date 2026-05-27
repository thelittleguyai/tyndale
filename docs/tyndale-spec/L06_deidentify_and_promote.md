# Task L06 — De-identify & promote pipeline

**Phase:** L2 · V1-Lite new (feedback loop, stages 2–4)
**Who:** Brock + Claude Code
**Estimated time:** 1.5 hours
**Depends on:** L05, plus full Build Kit Task 26 (golden schema) and the developer spec §18 (Presidio)

## What this task does

Builds stages 2–4 of the feedback loop: de-identification (the HIPAA gate), triage, and promotion into the eval suite. This turns real usage into labeled eval cases that make every future version better. Forward-compatible with full Tyndale.

## Prompt to paste into Claude Code

```
Build the de-identification, triage, and promotion pipeline for Tyndale's
feedback loop. This converts consented, de-identified real cases into
golden eval examples.

First read:
- feedback/capture_schema.json
- feedback/consent_model.md
- evals/golden/schema.json
- evals/golden/README.md
- reference/discipline_rules.md (D18 PHI/Presidio rules)

Create these files:

1. `feedback/pipeline_spec.md` — the full pipeline specification:

# Feedback Pipeline: De-identify → Triage → Promote

## Stage 2 — De-identify (the HIPAA gate)

Every candidate case (improvement_consent = true) passes through
de-identification BEFORE a human ever reviews it for promotion:

- Run the same Presidio + custom-recognizer pipeline from the developer
  spec §18 over: the uploaded document text (OCR'd), the extracted
  values, the case file findings, and any free-text feedback.
- Custom recognizers: insurance member IDs, MRNs, accession numbers,
  payer claim IDs, account numbers, group numbers (same set as §18).
- Replace direct identifiers with typed placeholders (e.g., [MEMBER_ID],
  [PATIENT_NAME], [DOB]) while preserving the structure that makes the
  case useful as an eval (codes, amounts, dates-relative, error patterns).
- A case that fails de-identification (Presidio confidence below
  threshold, or manual flag) does NOT proceed. It stays in the encrypted
  audit log only.

CRITICAL: de-identification is required even WITH consent. Consent
permits improvement use; de-identification makes the data safe for it.
Both are required (per consent_model.md rule 4).

## Stage 3 — Triage

De-identified candidates enter a triage queue for Brock's review:

- Negative feedback / corrections are HIGH priority — they reveal failure
  modes worth testing against.
- Value-confirmation corrections (user fixed an extracted number) are
  HIGH priority — they reveal extraction weaknesses.
- Positive feedback on hard cases is MEDIUM priority — good guardrail
  candidates.
- Routine positive feedback is LOW priority — sampled, not exhaustively
  reviewed.
- Triage routes to #tyndale-quality (the same channel from the full
  failure-mode instrumentation, §22).

Triage decision per case: promote / discard / needs-expert-review
(route hard legal/billing calls to the contracted attorney or advocate).

## Stage 4 — Promote into the eval suite

Promoted cases are written as golden examples matching
evals/golden/schema.json:
- A case Tyndale got WRONG becomes a regression test (expected_output_traits
  capture the CORRECT behavior the next version must produce).
- A case Tyndale got RIGHT becomes a guardrail (future changes can't
  break it).
- Set author to "production_feedback" (a new author enum value — update
  evals/golden/schema.json to add it).
- Link back via the feedback event's linked_golden_example_id and set
  promoted_to_eval = true.

This implements discipline rule D21.10 ("eval suite grows from production
findings") with a real pipeline.

## Forward compatibility

This pipeline is identical in V1-Lite and full Tyndale. Full Tyndale
inherits it running, plus all the cases V1-Lite already accumulated.
The only difference is volume.

2. `feedback/triage_runbook.md` — a practical runbook for Brock's
   weekly triage session:
   - How to pull the triage queue
   - What to look for in each priority tier
   - How to write a promoted case (reference the EXAMPLE.json from Task 26)
   - When to route to the attorney/advocate
   - How to record the triage decision back to the feedback event
   - Target cadence: weekly, alongside the failure-mode alert review (D22.4)

3. `feedback/deidentify_runner.py` — a Python script template:

```python
"""
De-identification runner for the Tyndale feedback pipeline.

Processes consented feedback cases through Presidio + custom recognizers,
producing de-identified candidate eval cases for triage.

This is a TEMPLATE. The engineering team wires in the actual Presidio
pipeline (shared with the runtime §18 implementation) and the feedback
data store.

USAGE:
    python deidentify_runner.py --since <date> [--dry-run]
"""

import argparse
# TODO: import shared Presidio pipeline from the runtime PHI module
# TODO: import feedback data store client

CONFIDENCE_THRESHOLD = 0.95  # matches §18 direct-identifier recall target

def load_consented_cases(since):
    """Load feedback cases with improvement_consent=true since <date>."""
    raise NotImplementedError  # engineering wires in the data store

def deidentify_case(case):
    """
    Run Presidio + custom recognizers over all text fields.
    Returns (deidentified_case, passed: bool).
    A case fails if any field's de-id confidence is below threshold.
    """
    raise NotImplementedError  # engineering wires in shared §18 pipeline

def queue_for_triage(deidentified_case):
    """Write the de-identified case to the triage queue."""
    raise NotImplementedError

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cases = load_consented_cases(args.since)
    passed, failed = 0, 0
    for case in cases:
        deid, ok = deidentify_case(case)
        if ok:
            if not args.dry_run:
                queue_for_triage(deid)
            passed += 1
        else:
            failed += 1  # stays in encrypted audit log only
    print(f"De-identified: {passed} queued, {failed} failed (retained in audit log only)")

if __name__ == "__main__":
    main()
```

4. Update evals/golden/schema.json to add "production_feedback" to the
   author enum.

5. Update evals/golden/README.md to add a section "Cases from production
   feedback" explaining that the feedback pipeline promotes real
   de-identified cases into this suite, and that these are often the
   highest-value examples because they reflect real failure modes.

Update MODES.md to list feedback/ files as mode: universal.

Commit with message "Add de-identify, triage, and promotion pipeline for feedback loop".
```

## Done when

- `feedback/pipeline_spec.md`, `triage_runbook.md`, `deidentify_runner.py` exist
- The de-identification-required-even-with-consent rule is explicit
- `evals/golden/schema.json` has the `production_feedback` author value
- `evals/golden/README.md` references the feedback pipeline
- Git log shows the commit

## Next task

[Task L07 — Encounter verification flow](L07_encounter_verification.md)
