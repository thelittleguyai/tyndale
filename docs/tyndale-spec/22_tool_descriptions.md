# Task 22 — Build all 22 tool descriptions

**Phase:** 4 · Tool descriptions
**Who:** Brock + Claude Code
**Estimated time:** 3–4 hours
**Depends on:** Phases 1, 2, 3 complete

## What this task does

Creates the tool description files for all 22 tools. Anthropic's published data showed that rewriting tool descriptions cut downstream task completion time by 40% — so these matter. Brock authors them; engineers implement the actual Python code.

## Prompt to paste into Claude Code

```
Create the tool description files in `tools/descriptions/`. There are 22
tools organized into 10 categories. Create one Markdown file per tool.

Each file follows this exact structure:

# tool_name

## What it does
[One sentence — concrete, specific]

## When to use
[Bullet list of positive triggers. When SHOULD a subagent call this tool?]

## When NOT to use
[Bullet list of exclusions. What looks like a use case but isn't?]

## Arguments
[Each argument with type, description, and a concrete example]

## Returns
[The return shape with a concrete sample]

## Errors and edge cases
[What can go wrong; how the tool surfaces problems]

## Used by
[Which subagents have this tool in their allow-list]

---

Here are the 22 tools to document, organized by category:

### Bill ingestion / OCR
1. bill_ocr_extract
   - Args: bill_image_id (UUID of uploaded bill image in Postgres)
   - Returns: extracted_text (string), structured_fields (dict with
     provider_name, dates, charges, totals, codes)
   - Used by: Bill Detective

### FHIR (via 1upHealth)
2. fhir_oauth_initiate
   - Args: user_id, payer_id
   - Returns: oauth_url (string) for user redirect
   - Used by: Lead Planner (initiates), engineers' code handles callback

3. fhir_get_coverage
   - Args: user_id, as_of_date (optional, defaults to today)
   - Returns: list of Coverage resources
   - Used by: Math Person, Lead Planner

4. fhir_get_eobs
   - Args: user_id, date_range (start, end), payer (optional)
   - Returns: list of ExplanationOfBenefit resources
   - Used by: Bill Detective, Math Person

5. fhir_get_clinical_note
   - Args: user_id, encounter_id (optional), date_range (optional)
   - Returns: list of clinical notes (typically restricted by user permission)
   - Used by: Legal Researcher (for medical-necessity context)

### Qdrant retrieval (knowledge collections)
6. qdrant_search_billing_codes
   - Args: query, max_results (default 10)
   - Returns: list of matching code records with descriptor + metadata
   - Used by: Bill Detective, Code Validator

7. qdrant_search_error_detection_rules
   - Args: query, applicable_codes (optional), max_results (default 10),
     effective_date (defaults to today for new questions)
   - Returns: list of matching rule narratives
   - Used by: Bill Detective

8. qdrant_search_laws_regulations
   - Args: query, jurisdiction (optional), effective_date (REQUIRED — hook blocks queries without this), max_results (default 10)
   - Returns: list of matching statute/regulation chunks with metadata
   - Used by: Legal Researcher

9. qdrant_search_payer_policies
   - Args: query, payer, effective_date (REQUIRED — hook blocks queries without this), applicable_codes (optional), max_results (default 10)
   - Returns: list of matching policy chunks with metadata
   - Used by: Bill Detective, Math Person, Legal Researcher

### Postgres case files
10. pg_case_file_get
    - Args: case_file_id OR (user_id, status_filter)
    - Returns: case file record or list of records
    - Used by: All subagents

11. pg_upsert_finding
    - Args: case_file_id, finding (structured dict), subagent_source
    - Returns: finding_id
    - Used by: All subagents

12. pg_deadline_upsert
    - Args: case_file_id, deadline_date, deadline_type, description
    - Returns: deadline_id
    - Used by: Strategist (primarily), Lead Planner

13. pg_list_due
    - Args: user_id (optional), within_days (default 30)
    - Returns: list of upcoming deadlines
    - Used by: Lead Planner, Strategist, Proactive Monitor cron

14. pg_document_template_get
    - Args: template_id (letter type)
    - Returns: template content with variable placeholders
    - Used by: Document Generation Skill via Strategist

### Cost estimation
15. cost_estimate_fair_health
    - Args: cpt_code, geographic_zip (3-digit if no BAA, full if BAA executed)
    - Returns: FAIR Health UCR estimate with confidence band
    - Used by: Math Person, Lead Planner (direct via Cost Estimation Skill)

16. cost_estimate_medicare_rvu
    - Args: cpt_code, geographic_locality
    - Returns: Medicare allowable rate
    - Used by: Math Person, Lead Planner

### Code & bundling (structured Postgres tables)
17. ncci_check_pair
    - Args: code_a, code_b, date_of_service
    - Returns: bundling_status (bundled | not_bundled | modifier_allowed),
      applicable_modifier, NCCI edit reference
    - Used by: Bill Detective, Code Validator

18. mue_check
    - Args: code, units_billed, date_of_service
    - Returns: within_limit (boolean), mue_value, rationale
    - Used by: Bill Detective, Code Validator

### Legal lookups
19. legal_doi_complaint_route
    - Args: user_state, payer_type (commercial | medicaid | medicare | self_funded)
    - Returns: applicable DOI office info, complaint procedure summary
    - Used by: Legal Researcher, Strategist

20. deadline_calculate
    - Args: triggering_event_date, deadline_type (erisa_internal_appeal |
      aca_external_review | nsa_negotiation | nsa_idr | ...), jurisdiction
    - Returns: calculated_deadline_date with reasoning
    - Used by: Strategist (primarily), Lead Planner

### 340B & charity care
21. provider_340b_check
    - Args: provider_npi OR provider_name + state
    - Returns: is_340b_eligible (boolean), 340B program participation details
    - Used by: Strategist (when 340B-pricing arguments may apply)

22. charity_care_eligibility
    - Args: provider_npi, user_household_income, user_household_size,
      state, asset_test_relevant (boolean)
    - Returns: preliminary_eligibility (eligible | likely_eligible |
      likely_ineligible | needs_more_info), reasoning, applicable FAP_url
    - Used by: Strategist

### Document generation
23. doc_template_select
    - Args: letter_type (one of 21 enum values), case_file_id
    - Returns: selected template, list of required structured inputs
    - Used by: Strategist

24. doc_generate
    - Args: template_id, structured_inputs (dict matching template requirements),
      case_file_id
    - Returns: generated_document_id, plain_language_summary, formal_body
    - Used by: Strategist (gated by user approval before send_email)

### Email & notifications
25. compose_email
    - Args: case_file_id, document_id, recipient (string — payer/provider/DOI),
      subject_line
    - Returns: composed_email_id (NOT yet sent — requires explicit approval)
    - Used by: Strategist

26. send_email (GATED by PreToolUse hook)
    - Args: composed_email_id, approval_token (validated by hook)
    - Returns: send_status, postmark_message_id
    - Used by: Lead Planner (after user approval)

27. notify_user
    - Args: user_id, urgency_tier (urgent | action | success | info),
      channel (sms | push | email | in_app), message_template_id,
      template_vars
    - Returns: notification_id
    - Used by: Lead Planner, Proactive Monitor cron

Note: tools 23-27 brings the total to 27. If the count exceeds the "~22"
listed in the developer spec, that's fine — the developer spec said
"~22" intentionally because the exact count was being finalized as
descriptions were authored. Update the developer spec's tool inventory
to match the final count after this task completes.

For each tool, write a 30-50 line description file with all the sections
above. Use concrete examples in the Arguments and Returns sections — not
generic placeholders. Make the descriptions detailed enough that a
subagent's first invocation can succeed without a "let me check the
schema" round trip.

Commit with message "Add all tool descriptions (Phase 4 complete)".
```

## Done when

- `tools/descriptions/` contains a Markdown file for each of the 27 tools
- Each file has all 7 sections (What it does, When to use, When NOT to use, Arguments, Returns, Errors, Used by)
- Git log shows the commit

## Next task

[Task 23 — Collection metadata schemas](23_collection_schemas.md)
