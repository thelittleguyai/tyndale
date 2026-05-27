# Task 26 — Build the golden examples folder structure

**Phase:** 6 · Eval test data
**Who:** Brock + Claude Code
**Estimated time:** 45 minutes
**Depends on:** Phases 1–5 complete

## What this task does

Sets up the directory structure and JSON schema for golden eval examples. Doesn't author the examples themselves (Task 27 does that); just creates the scaffolding so when examples get authored, they have a place to go.

## Prompt to paste into Claude Code

```
Create the directory structure and schema for golden eval examples
under `evals/golden/`.

Directory structure to create:

evals/golden/
├── README.md
├── schema.json
├── per_skill/
│   ├── bill_error_detection/
│   ├── document_generation/
│   ├── negotiation_strategy/
│   ├── charity_care_eligibility/
│   ├── cost_estimation/
│   ├── coverage_connection_fhir/
│   ├── find_a_doctor/
│   └── plan_a_visit/
├── per_subagent/
│   ├── lead_planner/
│   ├── bill_detective/
│   ├── math_person/
│   ├── legal_researcher/
│   ├── strategist/
│   └── code_validator/
└── voice_and_safety/
    ├── tier_a_factual/
    ├── tier_b_legal/
    ├── tier_c_strategic/
    ├── refusal_correctness/
    └── confident_voice_rubric/

For schema.json:

JSON Schema defining a golden example:

{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Golden Eval Example",
  "type": "object",
  "required": ["id", "category", "input", "expected_output_traits", "author", "authored_date"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^gold_[a-z0-9_]{4,}$",
      "description": "Unique identifier, e.g., 'gold_bundling_001'"
    },
    "category": {
      "type": "string",
      "enum": [
        "bill_error_detection",
        "document_generation",
        "negotiation_strategy",
        "charity_care_eligibility",
        "cost_estimation",
        "coverage_connection_fhir",
        "find_a_doctor",
        "plan_a_visit",
        "lead_planner",
        "bill_detective",
        "math_person",
        "legal_researcher",
        "strategist",
        "code_validator",
        "tier_a_factual",
        "tier_b_legal",
        "tier_c_strategic",
        "refusal_correctness",
        "confident_voice_rubric"
      ]
    },
    "subcategory": {
      "type": "string",
      "description": "Optional subcategory (e.g., 'bundling' under bill_error_detection)"
    },
    "input": {
      "type": "object",
      "required": ["user_message"],
      "properties": {
        "user_message": {
          "type": "string",
          "description": "What the user types/says"
        },
        "attached_documents": {
          "type": "array",
          "items": {"type": "string"},
          "description": "File paths to attached bills/EOBs/etc."
        },
        "case_file_state": {
          "type": "object",
          "description": "Optional pre-existing case file state"
        },
        "user_profile": {
          "type": "object",
          "description": "User context (plan, demographics, state)"
        }
      }
    },
    "expected_output_traits": {
      "type": "object",
      "description": "What the correct output looks like",
      "properties": {
        "should_contain": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Specific phrases or claims that must appear"
        },
        "should_not_contain": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Phrases or behaviors that must not appear (e.g., 'definitely', outcome predictions)"
        },
        "required_citations": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Authorities that must be cited"
        },
        "voice_tier_compliance": {
          "type": "object",
          "description": "Per-tier requirements"
        },
        "anticipated_next_steps_required": {
          "type": "boolean",
          "description": "Whether output must include P2 surfacing"
        },
        "factual_assertions": {
          "type": "array",
          "items": {"type": "object"},
          "description": "Specific factual claims that must be correct (e.g., 'member responsibility = $560')"
        }
      }
    },
    "expert_reasoning": {
      "type": "string",
      "description": "Why this is the correct answer; the reasoning trail that justifies the expected output"
    },
    "author": {
      "type": "string",
      "enum": ["brock", "contracted_attorney", "billing_advocate"]
    },
    "authored_date": {
      "type": "string",
      "format": "date"
    },
    "reviewed_by": {
      "type": "array",
      "items": {"type": "string"}
    },
    "difficulty": {
      "type": "string",
      "enum": ["easy", "medium", "hard", "adversarial"]
    },
    "notes": {
      "type": "string",
      "description": "Author notes about edge cases, etc."
    }
  }
}

For README.md:

# Golden Eval Examples

Expert-labeled examples used to evaluate Tyndale's intelligence layer.

## Structure

- per_skill/ — examples organized by Skill
- per_subagent/ — examples organized by subagent
- voice_and_safety/ — examples for voice tier compliance and refusals

## File naming

Use the pattern `<category>_<sequence>.json`:
- `bill_error_detection/bundling_001.json`
- `tier_b_legal/nsa_violations_002.json`

Each file contains ONE example matching schema.json.

## Authoring

- Brock authors most examples
- Contracted attorney authors complex legal-interpretation examples
- Billing advocate authors complex bill-detection examples

## Target counts at V1

~400 total examples across all categories. Specific targets:
- per_skill: ~50 per Skill (8 Skills = ~400 examples)
- per_subagent: ~30 per subagent (6 subagents = ~180 examples)
- voice_and_safety: ~50 examples total

(These overlap — a bill_error_detection example also tests
bill_detective. So actual unique example count is ~400-600.)

## Quality criteria

Every golden example must:
- Have a clear, testable expected_output_traits section
- Have author-provided expert_reasoning explaining why the answer is correct
- Be reviewed by a second author before merge

## How these get used

Braintrust evals run these against Tyndale's intelligence layer
every PR. Regression below baseline blocks merge.

The LLM judge (Opus 4.7) scores outputs against the expected_output_traits.
Cohen's κ ≥ 0.6 between judge and human reviewer is required for the
judge to be considered calibrated.

Add an example file at evals/golden/per_skill/bill_error_detection/EXAMPLE.json
that shows what a complete golden example looks like — use this as a
template for future examples.

The EXAMPLE.json should be:

{
  "id": "gold_bundling_example_001",
  "category": "bill_error_detection",
  "subcategory": "bundling",
  "input": {
    "user_message": "My doctor billed for both a wound repair and a separate excision on the same visit. Is that right?",
    "attached_documents": ["test_data/bills/bundling_example.pdf"],
    "case_file_state": {},
    "user_profile": {"plan_type": "commercial", "state": "UT"}
  },
  "expected_output_traits": {
    "should_contain": [
      "appears to violate",
      "NCCI",
      "CPT 12031",
      "CPT 11402"
    ],
    "should_not_contain": [
      "definitely fraud",
      "your appeal will succeed",
      "may possibly"
    ],
    "required_citations": ["NCCI PTP edit"],
    "voice_tier_compliance": {
      "tier_a_assertions": "must include billed codes",
      "tier_b_legal": "must cite NCCI",
      "tier_c_recommendation": "must propose next step"
    },
    "anticipated_next_steps_required": true,
    "factual_assertions": [
      {"claim": "CPT 12031 and CPT 11402 are bundled per NCCI", "must_be_true": true}
    ]
  },
  "expert_reasoning": "The user describes a classic NCCI PTP edit scenario. CPT 12031 (intermediate wound repair) and CPT 11402 (excision benign lesion 1.1-2.0cm) are bundled — the excision is included in the repair on the same site. The correct output identifies the bundling, cites NCCI, and proposes a re-adjudication request.",
  "author": "brock",
  "authored_date": "2026-05-19",
  "difficulty": "medium",
  "notes": "Could also flag modifier 59 if used inappropriately to unbundle — but that's a separate eval."
}

Commit with message "Add golden eval structure and schema".
```

## Done when

- All directories exist under `evals/golden/`
- `schema.json` is a valid JSON Schema
- `README.md` exists with the authoring guidance
- `EXAMPLE.json` exists demonstrating the format
- Git log shows the commit

## Next task

[Task 27 — Golden examples authoring](27_golden_examples_authoring.md)
