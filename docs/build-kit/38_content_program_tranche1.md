# 38 · Content Program + Tranche 1 (priors table included, ready to ingest)

Brock → Phil · 2026-08-18 · The plan to fill the knowledge collections, and the first delivery. (Filed to build-kit 2026-08-22 by Cowork; canonical source for the Tranche 1 ingestion session.)

Context: the empty knowledge collections were identified as the binding constraint on quality. This document is (a) the sequenced delivery program for ingestion planning, (b) Tranche 1 delivered inline — the missing-data priors table with real sourced values, which flips user-visible ranges from placeholder to honest, and (c) one schema gap needing resolution before the error-rules tranche lands.

## 1 · The delivery sequence

Ordered by leverage.

| Tranche | Content | Collection / target | Unblocks | Status |
|---|---|---|---|---|
| 1 | Missing-data priors table | `missing_data_priors.py` | User-visible ranges become honest — highest urgency (placeholders currently render) | BELOW |
| 2 | Error-detection rules — payer-side adjudication checks | `error_detection_rules` | The checks that find payer errors (most distinctive capability) | Blocked on §3 schema gap |
| 3 | Error-detection rules — provider-side coding checks | `error_detection_rules` | Duplicates, upcoding, units, markup | After tranche 2 |
| 4 | Federal law: No Surprises Act core | `laws_regulations` | Balance-billing analysis; partial `enable_nsa_checks` | Next |
| 5 | 50-state seed, pass 1 (10 highest-population states) | `laws_regulations` | Full `enable_nsa_checks`; state-specific [B] claims | In progress |
| 6 | Coverage-population rules (7 populations) | `payer_policies` | Correct rules per plan type — the regime-switcher gate | After 4 |
| 7 | COB / secondary-insurance logic | `payer_policies` | The primary→secondary computation gap | After 6 |
| 8 | Payer medical-policy bulletins | `payer_policies` | "Your insurer's own policy says…" | Ongoing, harvest-driven |
| 9 | Billing codes | `billing_codes` | Code descriptors + NCCI/MUE | Gated on AMA CPT license |

Run the before/after sweep after tranche 2 — the first one that should move detection measurably. Tranche 1 changes honesty, not detection.

## 2 · TRANCHE 1 — The missing-data priors table (deliverable, real values)

Every value sourced. Where no defensible prior exists, the entry says so explicitly and must stay dark — a placeholder rendered on screen is a fabricated number.

*Status 2026-08-27: RECEIVED and live — 5/7 entries activated (deductible_amount, oop_max_amount, coinsurance_percent, copay_pcp, copay_specialist); copay_er + household_income dark by design.*

Structure per entry: `base`, `low`/`high`, `disclosure_tier` (0–3), `source`, `as_of`, `confidence`, `activate` (per-entry flag).

### 2.1 Rate substitutions (all Tier 3 — range only, never a point)

| Entry | base | low | high | Source | as_of | Activate |
|---|---|---|---|---|---|---|
| `hospital_outpatient_pct_medicare` | 279% | 165% | 300% | RAND Hospital Price Transparency Round 5.1 (Dec 2024, 2022 data) | 2024-12 | ✓ |
| `hospital_inpatient_pct_medicare` | 254% | 165% | 300% | RAND Round 5.1 | 2024-12 | ✓ |
| `physician_pct_medicare` | 140% | 118% | 179% | MedPAC March 2025 Report, Ch. 4 | 2025-03 | ✓ |
| `imaging_pct_medicare` | 155% | 150% | 160% | Single-study 2025 | 2025 | low confidence — activate with Tier 3 language only |
| `lab_pct_medicare` | — | — | — | No aggregate multiple exists | — | DO NOT ACTIVATE. Never quote a lab multiple. Medicare rate as floor-only framing. |
| `regional_average_substitution` | — | — | — | HCCI: within-market spread averages 2.7× low-to-high; outliers 6–10× | 2025 | Ranges only. A point estimate on a regional substitution is dishonest by this spread alone. |

### 2.2 Coverage-term substitutions

| Entry | base | low | high | Tier | Source | as_of |
|---|---|---|---|---|---|---|
| `deductible_single` | $1,886 | $0 | $2,000+ | 2–3 (by computed swing) | KFF Employer Health Benefits Survey 2025. 12% have $0; 34% have ≥$2,000 — the distribution matters more than the mean. | 2025-10 |
| `oop_max` | $4,000 | $2,000 | $6,000+ | 1–2 (by computed swing) | KFF EHBS 2025. 12% ≤$2k; 21% >$6k. Matters only near the cap. | 2025-10 |
| `coinsurance_rate` | 20% | 19% | 20% | 1 | KFF EHBS 2025 — 19% office, 20% hospital. Tight prior. | 2025-10 |
| `copay_pcp` | $27 | $0 | $75 | 0–1 | KFF EHBS 2025 | 2025-10 |
| `copay_specialist` | $45 | $0 | $75 | 0–1 | KFF EHBS 2025 | 2025-10 |
| `deductible_met_ytd` | — | — | — | 2–3 | No prior — compute the range across plausible values per case. The classic load-bearing unknown. | — |
| `family_deductible_structure` | — | — | — | Ask when triggered | No reliable prior. Only ask when family plan + multiple members' claims are both present; otherwise irrelevant. | — |

### 2.3 Mechanically resolvable — resolve, don't estimate

| Entry | Handling | Source |
|---|---|---|
| `medicare_participation` | Tier 0 — resolve via the CMS opt-out NPI dataset, don't disclose. Prior 98% participating; opt-out 1.2% overall but concentrated: psychiatry 8.1%, plastic surgery 4.5%. Run the NPI match, specialty-aware. | CMS opt-out file (Nov 2024 data) |
| `grandfathered_status` | Tier 0 — assume non-grandfathered silently per the Check-10 lock; record internally. Prior stale (36% in 2013, declining). Mitigation: check the SBC silently when present. | — |

### 2.4 Regime-switchers — NOT priors. Never default these.

They change which rules apply; they go through the verification ladder, and if unverifiable the branch is presented honestly. No entry may ever be silently defaulted.

| Entry | Why it's a switcher | Reference prior (internal risk-ranking only — never user-facing as an assumption) |
|---|---|---|
| `network_status` | Wrong guess flips the case entirely ($60 vs $1,800) | 85–95% in-network routine; 70–90% for ER, anesthesia, pathology, assistant surgeons — precisely where surprise bills live. |
| `coverage_population` | Flips the entire rules corpus | None permissible — detect at intake |
| `screening_vs_diagnostic` | Determines whether $0 preventive applies | Per Check-10 lock: infer → one question → script |
| `nsa_plan_type` (self-funded ERISA vs. state-regulated) | Determines which law and which appeal channel | Checkable fact |
| `emergency_status` | Triggers NSA protections | Prudent-layperson standard; never collect symptoms |

### 2.5 The tier → rendering contract

| Tier | Trigger | Renders as |
|---|---|---|
| 0 | Near-certain or mechanically resolved, swing below materiality | Nothing user-facing. Internal record only. |
| 1 | Below materiality but user-correctable, or tight-prior substitute | One inline clause, no push: "I assumed 20% coinsurance — the norm; if yours differs this moves about $14 per $1,000 of allowed charges." |
| 2 | Computed swing above $100 or 10% | Name it, show the computed range, one easiest-path push: "Without your deductible-met figure, your share could be $290–$1,140 — that one number is worth pinning down." |
| 3 | Any benchmark substitution | Full pattern, range only, never a point: name the substitute + why + range + the tighten-path. |

Tier assignment is computed, never authored. The engine computes the swing using these priors; $100/10% splits Tier 1 from 2; benchmark substitution forces Tier 3. The model never decides how confident to sound.

### 2.6 Activation rule

Activate an entry only when it has a real sourced value above. Entries marked ✗ or "no prior" stay dark — the range simply isn't offered, and the audit degrades to asking the user instead. Better to ask than to invent.

## 3 · Schema gap — needs resolving before Tranche 2

`error_detection_rules` as specced is provider-side coding oriented: `rule_type` examples are `ncci_ptp`, `mue`, `modifier_validity`, and `applicable_codes` is required. About half the locked checks are payer-side adjudication errors — deductible applied wrong, OOP-max ignored, in-network processed as out-of-network, wrong coinsurance rate, auth on file ignored. These are the most distinctive capability (errors users never suspect because they arrive on official insurer letterhead) and have no natural home: they aren't code-specific, so `applicable_codes` is meaningless.

Proposed resolution — extend rather than replace:
- Add `rule_class` (enum): `provider_coding` | `payer_adjudication` | `legal_protection` | `pricing`
- Make `applicable_codes` optional (required only when `rule_class = provider_coding`)
- Add `responsible_party` (enum): `provider` | `payer` | `either` — feeds the UI's finding attribution per the master UX spec
- Add payer-side `rule_type` values: `deductible_misapplication`, `oop_max_ignored`, `network_status_misapplied`, `coinsurance_rate_error`, `auth_on_file_ignored`, `allowed_amount_above_contract`, `cob_misordering`

**Status 2026-08-22: CONFIRMED by engineering as proposed — see `reply_to_brock_2026-08-22_tranche1.md`. Tranche 2 authors against the extended shape.**

## 4 · What Brock needs back

1. ~~Confirm the §3 schema extension~~ — CONFIRMED 2026-08-22.
2. ~~Confirm the priors ingestion path~~ — CONFIRMED: JSON tranche files; loader already live in `missing_data_priors.py`.
3. Still outstanding: the three draft files → delivered to `Tyndale Final/` 2026-08-19; awaiting his A1–A7 review.

## 5 · Sources for §2 (all verifiable)

RAND Hospital Price Transparency Round 5.1 (Dec 2024) · MedPAC March 2025 Report Ch. 4 · KFF Employer Health Benefits Survey 2025 (Oct 2025) · HCCI within-market price-variation analysis (2025) · KFF Medicare opt-out analysis (2025, CMS Nov 2024 data) · Yale Tobin out-of-network billing studies.

Known research gaps, tracked: KFF 2025 full chartbook (OOP-max distribution detail, copay-vs-coinsurance split, ER cost-sharing, embedded-vs-aggregate family deductible share, current grandfathered share). Never quote a lab multiple until sourced. Re-verify the RAND multiple at Round 5.2.
