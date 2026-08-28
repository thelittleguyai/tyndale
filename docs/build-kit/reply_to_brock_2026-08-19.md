# Phil → Brock: response received — files landed, statuses below (2026-08-19)

## First: your A1–A7 blocker is cleared
All five files are now in `Tyndale Final/`: `33_orchestration_script_v2_DRAFT.md` · `37_x_rules_contracts_DRAFT.md` · `brock_decision_packet_2026-08-12.md` · `round2_delta_inventory.md` (annotated) · `COWORK_DRAFTS_ENG_REVIEW_2026-08-12.md`. Agreed: the build kit is the channel, both directions, from now on. Your one-day clock starts now.

## Your decisions are in implementation today
§3.11 renders verbatim (staging boot unblocks); §10.5's resources line comes out (DL-04 stands — the clean decline was never unwired, so nothing user-facing changes); B3 headline + C3/C4/D1 landing changes; **B5 is exactly the split we needed** — `finding.fact [A]` / `finding.rule_based [B]`, chips on legal claims only, §12.1 tagged `[B]`; enforcement turns on with this pass. A5's general rule (script is doctrine, checklist is a verification aid) is going into the conformance doc header so it outlives us both. Your priors-tranche design with dark-until-sourced entries matches the guard exactly — per-entry flags are already wired.

## The one-liner you asked for (nudge split)
The old single cron became two: the document **chase** (engineering voice — it must name the missing document) and your §11.5 **check-in** (your copy verbatim; fires only when the audit is complete AND an actionable gameplan exists AND no outcome has been reported; the chase wins when both premises hold; suppressed once the user reports a call). **Confirm that split and §3.8 closes.**

## §4 status sweep — evidence per claim, UNKNOWN where unverified
| Item | Status | Evidence |
|---|---|---|
| Negotiated-rate ingestion (MRF/TiC/Turquoise) | **PARTIAL** | `ingestion/parsers/hospital_mrf.py`, `transparency_rates` table (migration 0011), `hospital_mrf` + `medicare_pfs` crons scheduled. TiC/Turquoise-proper coverage and how much has actually RUN on dev: UNKNOWN — chunk 3 will say precisely. |
| CMS Exchange PUFs (BenCS + Plan) | **NOT STARTED** | zero references |
| EOB-derived benefits | **BUILT** | `sources/adapters/computed_from_uploaded_eobs.py` + `eob_stated_ytd.py`, three-way cross-validation (DL-72/80) |
| Plan Library (structured SBC reuse) | **BUILT** | `sources/adapters/plan_library.py` + `user_uploaded_sbc.py`, CO-12C propose/confirm, no-source-mention rule tested. Group-number keying specifics: verify in chunk 3. |
| Card OCR | **BUILT** | `sources/insurance_card.py` (Azure healthInsuranceCard), capture flow in settings |
| NPPES lookup | **NOT STARTED** | — |
| OIG LEIE + EXCLTYPE | **NOT STARTED** | (post-core per your own B8 scoping) |
| Google Places | **NOT STARTED** | — |
| Payer precert PDFs | **NOT STARTED** | — |
| Preventive lists (USPSTF/ACIP/HRSA, as-of-dated) | **PARTIAL** | rules-side skill exists (`preventive_violations.md`); the dated-constants ingestion of the lists themselves: not built |
| Proactive Monitor 8 triggers | **NOT STARTED** | spec-only; zero code hits |
| Outcomes data model | **BUILT** | outcome capture at tap (idempotent, typed, no-money-by-type), `outcome_followup` cron, follow-up card, analytics events |
| Payer adjudication patterns | **NOT STARTED** | — |
| Two-consent + de-ID (L05/L06) | **PARTIAL** | consent model + retro-enqueue + `feedback_deid_candidates` BUILT; the de-id promotion RUNNER: not built |
| Verification-card ground truth | **PARTIAL** | every answer persists per case + per-question analytics (incl. not-sure rates); not yet exported as a labeled corpus — the data survives, the corpus job doesn't exist |

## §5 expanded scope — acknowledged, sequenced honestly
Proceeding, with the build order set by your own gates: the two counsel/BAA-gated items (Browserbase co-browse; SBC harvesting republication read) get seams and specs before code that touches PHI or copyright. First wave will be the free-data, high-leverage set: **Form 5500 registry (#4), payer medical-policy corpus (#2), DOI external-review outcomes (#10), hospital financial-assistance corpus (#11)** — all public data, all feed existing seams. #9 is heard and closed: no Stedi rail, and the provider-NPI eligibility idea is dead on arrival if it ever surfaces.

## §6 chunked audit — protocol accepted as written
Spec-first enumeration, evidence per claim, UNKNOWN as a valid answer, one chunk per pass, drift reported not reconciled. Chunk 1 (Intake & extraction) starts after the settings-completeness session lands; one report at a time to the build kit.

— Phil
