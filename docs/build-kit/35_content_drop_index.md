# Content drop — index (2026-08-03)

**Why this exists:** everything below was authored between July 2 and August 3 but was living in a working folder rather than here in the build kit. Memos referencing these files reached the team; the files themselves didn't. That's fixed — this is the canonical location and future content lands here directly.

---

## New numbered build-kit files

**`33_orchestration_script.md` — the D1 orchestration script.** Every system-authored string the chat thread renders, upload → resolution. Doctrine file: **render verbatim.** *(2026-08-27: v1.1, 245 lines — §8.4–8.5 unlock-more added, §10.5 amended per the 08-18 response. The staging boot gate is SATISFIED: zero placeholders and the §3.11 keys are authored.)*
- `{variables}` are the only runtime substitution — all real computed/extracted values, never guessed.
- Voice-tier tags `[A]/[B]/[C]` govern rendering and must not be stripped: `[B]` legal strings render **with their citation chip**; `[C]` strategy strings **never predict an outcome**.
- Contains the five newer chat states, including **§3 attest-and-proceed** (relationship menu, confirm line, decline path, three elevated edge-case prompts) — the compliance state flagged as missing.
- Also §5 data-quality states (illegible/partial, wrong-document, conflicting-data reconcile-first), §10 decline states, §12 external-program handoff.

**`34_rules_logic_locked_decisions.md` — the rules-logic spine.** Every locked decision from Batches 1–5, including cross-cutting rules **X1–X6**. This is the source doc previously identified as content debt — X1–X6 were never in the repo because this file had never been handed over. Machine-readable X-rule contracts (X1/X2/X3/X5 CI-assertable; X4/X6 judge-scored) follow as a separate drop.

---

## `research_companions/` — 23 primary-source research files

The sources cited by filename throughout the master handoff. Each is primary-source-verified, dated, with unverified claims flagged ⚠️ and a "Key sources" list.

**Engine / rules work:** `upcoding_escalation_research` · `negotiation_playbook_when_correct` (charity-care-first, show-the-map-never-ask-income) · `secondary_insurance_cob_research` (**the ordering rules vs. the non-duplication dollar math — grounds the COB computation gap**) · `tyndale_oop_calculation_method` · `tyndale_rules_engine_scenarios` · `missing_data_spectrum` · `medical_necessity_appeal_playbook` · `unprotected_bill_playbook`

**Coverage populations (7):** `coverage_rules_traditional_medicare` · `coverage_rules_medicare_advantage` · `coverage_rules_medicaid_duals` · `coverage_rules_uninsured_selfpay` · `coverage_rules_tricare_va` · `coverage_info_decision_tree` · `portal_navigation_guide`

**Law / compliance:** `legal_certainty_research_nsa` · `network_deficiency_research` (plan-type-gated entitlement) · `previsit_requirements_research` · **`third_party_bill_authorization_research`** (grounds the attest-and-proceed state and the retention schedule — HIPAA personal-representative template, FTC HBNR, CMIA, WA MHMDA)

**Proactive features (post-core):** `proactive_monitor_blueprint` · `getting_a_concrete_price_research` · `find_a_doctor_feature_demand` · `oig_exclusion_reasons_research`

---

## Added 2026-08-03 (same drop, second pass)

**`36_design_conformance_checklist.md`** — pass/fail acceptance checklist for everything approved July 10–16: palette (exact hexes), landing page, upload, chat-first mechanics D0–D7, the reveal/unlock moments, the five newer chat states, orchestration rendering rules, Record/case/call-mode, and the first-case entitlement boundary. Walk the live app with it; return the ❌ list — deviations get a deliberate call, never silent drift.

**`research_companions/` additions:** `brock_to_phil_chatfirst_decisions_2026-07-10.md` (the D0–D7 sign-off the checklist cites) · `claude_design_prompt_tyndale_flow.md` (the approved flow spec with exact copy/numbers) · `ux_user_flow_research_2026-07-09.md` · **`brock_to_phil_master_handoff_2026-07-16.md`** (restored — the memo's content reached Phil July 16 but the file never persisted; this is the canonical copy, with references repointed to build-kit paths).

*Known gap, flagged honestly: the approved v7 landing-page HTML mockup did not survive to disk. Its approved values are encoded as checklist §A–B items, which are the reference. Regenerable on request.*

## Still owed (lands here, in this order)
1. ~~**`37_x_rules_contracts.md`** — X-rules machine-readable contracts~~ *(struck 2026-08-27: the DRAFT landed 08-12; the X5 enum is implemented in doctrine_config with the derived_draft escape hatch — what remains owed is Brock's SIGN-OFF on the taxonomy, not the document)*
2. B-series rules content — B4 extreme markup, B5 charity care, **B6 COB primary→secondary computation**
3. 50-state seed, pass 1
4. Judge rubric
