# Task L05 — Feedback capture & consent schema

**Phase:** L2 · V1-Lite new (feedback loop, stage 1)
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** L01, plus full Build Kit Task 26 (golden examples schema)

## What this task does

Builds stage 1 of the feedback & learning loop: the capture schema and the consent model. This is the foundation that lets V1-Lite learn from real users and real bills from the first day. It's forward-compatible — full Tyndale uses the identical schema.

## Prompt to paste into Claude Code

```
Build the feedback capture schema and consent model for Tyndale's
learning loop. This is new to both versions but built in V1-Lite first.

First read:
- evals/golden/schema.json (the capture schema must map cleanly to this)
- reference/discipline_rules.md (D18 PHI rules, D19 BAA rules)
- v1_lite/01_v1lite_scope_and_compatibility.html (Section 06, the loop design)

Create these files:

1. `feedback/capture_schema.json` — JSON Schema for a feedback event:

{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Tyndale Feedback Event",
  "type": "object",
  "required": ["event_id", "timestamp", "case_file_id", "feedback_type"],
  "properties": {
    "event_id": {"type": "string"},
    "timestamp": {"type": "string", "format": "date-time"},
    "case_file_id": {"type": "string"},
    "user_id": {"type": "string"},
    "response_id": {"type": "string", "description": "Which Tyndale response this is about"},
    "feedback_type": {
      "type": "string",
      "enum": ["thumbs", "structured_correction", "outcome_report", "value_confirmation", "implicit_signal"]
    },
    "thumbs": {"type": "string", "enum": ["up", "down"]},
    "structured_reason": {
      "type": "array",
      "items": {"type": "string", "enum": [
        "wrong_number", "missed_an_error", "false_error",
        "bad_recommendation", "confusing", "wrong_citation",
        "wrong_coverage_reading", "other"
      ]}
    },
    "free_text": {"type": "string", "description": "Optional user explanation"},
    "outcome": {
      "type": "object",
      "description": "Did the recommendation work?",
      "properties": {
        "acted_on_recommendation": {"type": "boolean"},
        "resolved": {"type": "string", "enum": ["yes", "no", "partial", "pending", "unknown"]},
        "amount_saved": {"type": "number"},
        "outcome_notes": {"type": "string"}
      }
    },
    "value_confirmation": {
      "type": "object",
      "description": "User confirming/correcting an extracted value (from low-confidence extraction)",
      "properties": {
        "field": {"type": "string"},
        "tyndale_extracted": {"type": "string"},
        "user_corrected": {"type": "string"},
        "was_correct": {"type": "boolean"}
      }
    },
    "improvement_consent": {
      "type": "boolean",
      "description": "Whether the user has consented to use this case (de-identified) for product improvement"
    },
    "promoted_to_eval": {"type": "boolean", "default": false},
    "linked_golden_example_id": {"type": "string"}
  }
}

2. `feedback/consent_model.md` — the consent model documentation:

# Tyndale Feedback Consent Model

## Two distinct consents

Per HIPAA, using a user's data to SERVE them is different from using it
to IMPROVE the product. Tyndale collects these separately:

### Consent 1 — Service consent (required to use Tyndale at all)
Covers: using the user's uploaded documents and data to analyze their
bills, check coverage, and provide recommendations. Without this, Tyndale
can't function. Collected at signup.

### Consent 2 — Improvement consent (optional, opt-in)
Covers: using the user's DE-IDENTIFIED bills, feedback, and outcomes to
improve Tyndale's accuracy and train/evaluate future versions. This is
SEPARATE and OPTIONAL. The user can use Tyndale fully without granting it.
Collected as a clear, specific opt-in — never bundled into the service
consent, never pre-checked.

Suggested opt-in copy:
"Help make Tyndale better. With your permission, we'll use your bills and
your feedback — with all your personal information removed — to improve
how Tyndale catches errors. This is optional and you can change it anytime
in Settings. It never affects the service you receive."

## Rules

1. Improvement consent is opt-IN, never opt-out. Unchecked by default.
2. A user can revoke improvement consent at any time. On revocation,
   their data is removed from the candidate pool (already-promoted,
   fully de-identified eval cases that contain no PHI may remain, since
   they're no longer personal data — document this clearly in the privacy
   policy and confirm with counsel).
3. No case enters the improvement pipeline without improvement_consent = true.
4. Even WITH consent, de-identification (Task L06) runs before any case
   becomes a candidate eval example. Consent is necessary but not
   sufficient — de-identification is also required.
5. Service consent alone NEVER permits improvement use.

3. `feedback/capture_points.md` — where in the UX feedback is captured:

# Feedback Capture Points

- Thumbs up/down on every Tyndale response (lightweight, always present)
- "What was wrong?" structured-reason picker appears on thumbs-down
- Value confirmation prompts during low-confidence extraction (these
  double as feedback — the correction IS training data)
- Outcome follow-up: a few days after a recommendation, a lightweight
  "Did this get resolved?" prompt (per P2 — surface what's next)
- Implicit signals logged: did the user act, did they return, did they
  re-upload a corrected document

All capture writes a feedback event matching capture_schema.json. Events
link to the case_file_id and response_id so the full context is
recoverable (within the encrypted audit log) during triage.

Update MODES.md to list feedback/ files as mode: universal (the loop is
shared by both versions).

Commit with message "Add feedback capture schema and consent model".
```

## Done when

- `feedback/capture_schema.json` is a valid JSON Schema
- `feedback/consent_model.md` documents the two-consent model clearly
- `feedback/capture_points.md` lists the UX capture points
- The schema maps cleanly to the golden example schema
- Git log shows the commit

## Next task

[Task L06 — De-identify & promote pipeline](L06_deidentify_and_promote.md)
