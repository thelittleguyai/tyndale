# Tyndale Spec — Index

A reference copy of the full Tyndale source spec, imported verbatim during Phase 0 closure
from Brock's two source folders (54 files + 7 files = 61 documents, plus this INDEX).
Filenames are preserved exactly. Grouped below by purpose, one line per file.

## Acceptance narrative

- `how_tyndale_works_reference.md` — End-to-end acceptance narrative walking a real case through Tyndale; the "what good looks like" reference.

## Foundation & cross-cutting reference rules

- `02_principles.md` — The six interaction principles (P1–P6) plus the Independent Audit and Grounding & Graceful Degradation doctrines.
- `03_voice_tiering.md` — The three-tier voice: Tier A facts, Tier B cited legal claims, Tier C reasoned recommendations; no outcome predictions.
- `04_refusal_templates.md` — The five out-of-scope categories and their clean-decline templates (incl. crisis decline with no routing).
- `05_citation_format.md` — The machine-parseable citation format and the Layer-2 ship-gate resolution rules.
- `06_tyndale_glossary.md` — Canonical glossary of Tyndale domain terms.
- `07_discipline_rules.md` — All discipline rules from the 22 architectural decisions (D0–D22), consolidated for search.

## V1-Lite track

- `01_v1lite_scope_and_compatibility.html` — V1-Lite scope and its forward-compatibility contract with Full V1.
- `02_v1lite_build_kit_index.html` — Index of the V1-Lite (L-series) build tasks.
- `L01_orientation.md` — V1-Lite orientation: what the lite track builds and how it maps to Full V1.
- `L02_upload_extraction_tools.md` — Upload + OCR extraction tools (the `upload_extract_*` set matching the FHIR return shapes).
- `L03_manual_coverage_mode.md` — Manual coverage-entry mode for when FHIR/automatic coverage isn't available.
- `L04_collapsed_lead_planner.md` — The V1-Lite collapsed Lead Planner (folds in Legal Researcher + Strategist; thinking loop + lead-with-status).
- `L05_feedback_consent_schema.md` — Feedback capture schema and the two-consent model.
- `L06_deidentify_and_promote.md` — De-identify + promote pipeline that turns consented feedback into golden examples.
- `L07_encounter_verification.md` — Encounter verification by plain-language line-item confirmation (facts, not clinical judgment).
- `L08_web_app_shell.md` — The V1-Lite web app shell / dashboard scaffold.
- `L09_v1lite_handoff.md` — V1-Lite handoff brief.

## Full V1 build kit (overview + 32 tasks)

- `01_overview.html` — Full V1 build-kit overview.
- `02_developer_spec.html` — The full developer spec; underlying source of truth for the integration contracts.
- `03_build_kit_index.html` — Index of the Full V1 build-kit tasks (01–32).
- `01_repo_setup.md` — Task 01: intelligence-layer repo setup.
- `08_skill_bill_error_detection.md` — Task 08: Bill Error Detection Skill (payer- and provider-side errors + encounter verification).
- `09_skill_document_generation.md` — Task 09: Document Generation Skill (letter types; Full V1).
- `10_skill_negotiation_strategy.md` — Task 10: Negotiation & Strategy Skill.
- `11_skill_charity_care.md` — Task 11: Charity Care eligibility Skill.
- `12_skill_cost_estimation.md` — Task 12: Cost Estimation Skill.
- `13_skill_coverage_fhir.md` — Task 13: Coverage Connection Skill (FHIR + manual mode).
- `14_skill_find_a_doctor.md` — Task 14: Find a Doctor Skill.
- `15_skill_plan_a_visit.md` — Task 15: Plan a Visit Skill.
- `16_subagent_lead_planner.md` — Task 16: Lead Planner subagent system prompt.
- `17_subagent_bill_detective.md` — Task 17: Bill Detective subagent system prompt.
- `18_subagent_math_person.md` — Task 18: Math Person subagent (three-number independent audit).
- `19_subagent_legal_researcher.md` — Task 19: Legal Researcher subagent (Full V1).
- `20_subagent_strategist.md` — Task 20: Strategist subagent (Opus 4.7; Full V1).
- `21_subagent_code_validator.md` — Task 21: Code Validator subagent (Haiku 4.5; Full V1).
- `22_tool_descriptions.md` — Task 22: the ~27 tool descriptions.
- `23_collection_schemas.md` — Task 23: schemas for the four Qdrant collections.
- `24_ingestion_templates.md` — Task 24: ingestion templates for the collections.
- `25_test_fixtures.md` — Task 25: test fixtures.
- `26_golden_examples_structure.md` — Task 26: golden-examples structure.
- `27_golden_examples_authoring.md` — Task 27: golden-examples authoring guide.
- `28_synthetic_generation_prompts.md` — Task 28: synthetic-generation prompts.
- `29_synthetic_generation_runner.md` — Task 29: synthetic-generation runner.
- `30_readme.md` — Task 30: intelligence-layer README.
- `31_baa_tracker.md` — Task 31: BAA tracker.
- `32_handoff_brief.md` — Task 32: handoff brief.

## Cowork PM/PdM outputs

- `00_v1lite_build_plan_for_brock_approval.md` — The V1-Lite build plan approved by Brock (phases, decisions, scope).
- `01_phase0_detailed_spec.md` — Phase 0 detailed spec (monorepo layout + integration contracts + exit criteria).
- `02_phase0_closure_prompt.md` — Phase 0 closure prompt (this repo scaffold was built from it).
- `03_phase1a_intelligence_layer_foundations.md` — Phase 1A prompt: Brock's intelligence-layer foundation files (build-kit Tasks 01–07).
- `04_phase1b_frontend_scaffold.md` — Phase 1B prompt: Phil's frontend scaffold (Expo + Next.js marketing + auth + Plausible).
- `05_phase1c_runtime_skeleton.md` — Phase 1C prompt: Jonas's runtime skeleton (FastAPI + Postgres + routes + LiteLLM proxy skeleton).
- `06_phase1d_qdrant_knowledge_layer.md` — Phase 1D prompt: Josh's Qdrant knowledge layer (four empty collections + embeddings).

## Legal pack + change orders (from Additional Files/)

- `00_developer_cowork_notes.md` — Developer/Cowork working notes.
- `01_terms_of_service.md` — Terms of Service (launch candidate; pending counsel sign-off).
- `02_privacy_policy.md` — Privacy Policy (launch candidate; pending counsel sign-off).
- `03_improvement_consent.md` — Improvement/data-use consent (the second consent in the feedback loop).
- `04_state_specific_rights_addendum.md` — State-specific privacy rights addendum.
- `change_order_001_readds.md` — Change Order 001: the four behavioral additions folded into V1-Lite.
- `build_update_phil_versionA_wrapper_ready.md` — Version A adjustments + wrapper-readiness (companion of record to CO-004 + CO-002 FINAL): the four data-interface seams, the `Provenance` object, Claude-for-Healthcare connector calls, and what "wrapper-ready" means. Approved by Brock 2026-06-20; implemented as Phases CO-12A–D and decisions DL-68 through DL-71. **Note:** the standalone CO-004 change-order document is referenced as the companion here but is not yet in the workspace — import it verbatim when Brock provides it.
- `post_v1lite_agent_architecture_vision.md` — Parked post-V1-Lite "agent company" architecture vision.
