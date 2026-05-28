# Tool Descriptions — Index

The V1-Lite tool surface and the Full V1 deferred slots. Subagent prompts and future Claude Code
sessions read this first to see which tools exist. **21 active** (V1-Lite) + **10 deferred**
(Full V1 placeholders). Each active file follows the 7-section contract (What it does / When to
use / When NOT to use / Arguments / Returns / Errors and edge cases / Used by).

## Core case file (universal)
- `pg_case_file_get` — read a case file (or a user's filtered list), incl. research_log/findings.
- `pg_upsert_finding` — write/update a structured finding; returns finding_id.

## Upload path (V1-Lite)
- `upload_classify_document` — classify an upload (bill/EOB/card/SBC/…) to route extraction.
- `upload_extract_coverage` — extract coverage terms from card/SBC; **same shape as fhir_get_coverage**.
- `upload_extract_eob` — extract EOB data from an uploaded EOB; **same shape as fhir_get_eobs**.
- `upload_request_missing` — generate a specific, trivial request for a missing document (P1).
- `bill_ocr_extract` — OCR an uploaded bill via Azure Document Intelligence (universal).

## Knowledge retrieval — Qdrant (universal)
- `qdrant_search_billing_codes` — CPT/HCPCS/ICD-10 lookup by code/descriptor.
- `qdrant_search_error_detection_rules` — narrative billing-rule text.
- `qdrant_search_laws_regulations` — statutes/regulations; **effective_date REQUIRED (PreToolUse blocks)**.
- `qdrant_search_payer_policies` — payer medical-necessity policies; **effective_date REQUIRED (PreToolUse blocks)**.

## Code & bundling — Postgres (universal)
- `ncci_check_pair` — NCCI procedure-to-procedure bundling check for a code pair + DOS.
- `mue_check` — Medically Unlikely Edit units check for a code + DOS.

## Deadlines & notifications (universal)
- `pg_deadline_upsert` — write/update a deadline on a case.
- `pg_list_due` — list upcoming/overdue deadlines (drives app-open status + Proactive Monitor cron).
- `deadline_calculate` — compute a deadline date from a triggering event + type, with reasoning.
- `notify_user` — send a templated notification on a channel at an urgency tier.

## Cost estimation (universal)
- `cost_estimate_fair_health` — FAIR Health UCR band; **3-digit-ZIP fallback until BAA**.
- `cost_estimate_medicare_rvu` — Medicare allowable benchmark.

## Legal & 340B (universal — folded into the V1-Lite Lead Planner)
- `legal_doi_complaint_route` — state DOI office + complaint procedure for the plan type.
- `provider_340b_check` — whether a provider participates in the 340B program.

## Deferred to Full V1 (placeholders — not implemented in V1-Lite)

### FHIR (via 1upHealth)
- `fhir_oauth_initiate` — *deferred* — SMART-on-FHIR OAuth initiation.
- `fhir_get_coverage` — *deferred* — Coverage resources (V1-Lite uses `upload_extract_coverage`, same shape).
- `fhir_get_eobs` — *deferred* — EOB resources (V1-Lite uses `upload_extract_eob`, same shape).
- `fhir_get_clinical_note` — *deferred* — clinical notes (V1-Lite uses user encounter confirmation).

### Document generation
- `doc_template_select` — *deferred* — select a letter template.
- `doc_generate` — *deferred* — generate a document (gated before send).
- `pg_document_template_get` — *deferred* — fetch a letter template.

### Email (gated)
- `compose_email` — *deferred* — compose (not send) an email.
- `send_email` — *deferred* — send an email (PreToolUse approval-token gated).

### Charity care
- `charity_care_eligibility` — *deferred* — preliminary FAP eligibility (with the Charity Care Skill).
