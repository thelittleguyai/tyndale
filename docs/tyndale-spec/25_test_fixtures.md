# Task 25 — Build the test fixtures for collections

**Phase:** 5 · Knowledge collection scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 1 hour
**Depends on:** Task 24

## What this task does

Creates small, representative test fixtures for each collection. ~20 records per collection. Engineers use these for local development testing before connecting to full production data sources.

## Prompt to paste into Claude Code

```
Create JSON fixture files in `collections/fixtures/`:

1. `billing_codes_fixture.json` — ~20 representative codes
2. `error_detection_rules_fixture.json` — ~20 representative rule chunks
3. `laws_regulations_fixture.json` — ~20 representative law chunks
4. `payer_policies_fixture.json` — ~20 representative policy chunks

Each fixture file is a JSON array of records matching the schema from
collections/schemas/.

The fixtures should be REALISTIC and DIVERSE — covering different types
of content the production data will have. This is not just toy data;
it's the foundation for local development eval.

billing_codes_fixture.json should include:

E/M codes:
- 99213 (Office visit, established, low complexity)
- 99214 (Office visit, established, moderate complexity)
- 99285 (ER visit, high complexity)

Common procedures:
- 12031 (Layer closure of wounds)
- 11402 (Excision benign lesion)
- 27447 (Total knee arthroplasty)
- 73721 (MRI knee without contrast)
- 45378 (Colonoscopy, screening)
- 45380 (Colonoscopy, diagnostic with biopsy)

Lab and imaging:
- 80053 (Comprehensive metabolic panel)
- 85025 (CBC with differential)
- 71046 (Chest X-ray, 2 views)
- 71250 (CT chest without contrast)

Preventive:
- 99395 (Preventive visit, adult)
- G0008 (Influenza vaccine administration)
- G0438 (Annual wellness visit, initial)

HCPCS (drug + supplies):
- J3490 (Unclassified drug)
- A4253 (Blood glucose test strips)

ICD-10 (diagnosis):
- I10 (Essential hypertension)
- E11.9 (Type 2 diabetes without complications)

Each with full descriptor, category, effective_year (2024 or 2025),
valid_modifiers where applicable.

error_detection_rules_fixture.json should include:
- 3-4 NCCI PTP edits (narrative text — the structured pair lookup is in
  Postgres, but the policy reasoning text goes in Qdrant)
- 2-3 MUE narratives
- 2-3 modifier validity narratives (modifier 25, 59, 51)
- 2-3 ACA §2713 preventive list narratives
- 2-3 upcoding pattern narratives (E/M level documentation)
- 2-3 phantom charge red flag narratives

laws_regulations_fixture.json should include:
- ERISA §503 (29 C.F.R. § 2560.503-1) — claims procedure
- ACA §2713 (42 U.S.C. § 300gg-13) — preventive services
- ACA §2719 (42 U.S.C. § 300gg-19) — appeals and external review
- NSA §300gg-111 — surprise billing prohibition (multiple subsections)
- MHPAEA §1185a — mental health parity (multiple subsections)
- IRS §501(r)(4) — financial assistance policy
- IRS §501(r)(6) — billing limitations on nonprofit hospitals
- EMTALA §1395dd — emergency screening obligation
- 1-2 state surprise-billing statutes (e.g., Cal. Health & Safety Code §1371.9)
- 1-2 state DOI complaint procedural statutes

Each chunk:
- ~800-1500 tokens of statute/regulation text
- Includes parent Title/Part/Subpart heading at the top
- Has effective_date_start and effective_date_end fields
- Has document_type set appropriately

payer_policies_fixture.json should include:
- 3-4 Medicare LCDs/NCDs (e.g., LCD for MRI of knee, NCD for screening colonoscopy)
- 3-4 commercial medical-necessity policies (synthesized examples
  styled like real UHC/Anthem/Aetna policies, but clearly marked as
  fixture data — NOT scraping real proprietary content)
- 2-3 prior-auth requirement summaries
- 1-2 formulary entries (drug coverage)

Each chunk follows payer_policies schema with effective dates, version,
payer name.

IMPORTANT — copyright note:
Real CPT descriptors and real payer policy text are subject to copyright
(CPT is AMA-owned; payer policies are proprietary). For the fixtures:
- billing_codes: use generic descriptors close to but not verbatim from
  CPT codebook
- error_detection_rules: use paraphrased policy text, not verbatim
- laws_regulations: federal statutes and regulations are public domain;
  verbatim is fine
- payer_policies: use clearly-synthesized examples, not real verbatim
  policies

Mark every fixture file with a top-level "_meta" comment block
indicating it's fixture data and noting the date created.

After creating all 4 fixture files, also create
`collections/fixtures/README.md` explaining:
- These are fixtures for local development testing only
- Production ingestion uses the scripts in collections/ingestion/
- Engineers must replace fixtures with real data before any production
  use
- Each fixture has ~20 records (intentionally small for fast local iteration)

Commit with message "Add collection test fixtures".
```

## Done when

- 4 fixture JSON files exist in `collections/fixtures/`
- Each contains ~20 realistic, diverse records
- README explains how to use them
- Git log shows the commit

## Next task

[Task 26 — Golden examples structure](26_golden_examples_structure.md)
