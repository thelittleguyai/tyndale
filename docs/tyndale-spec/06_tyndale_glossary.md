# Task 06 — Write the Tyndale glossary

**Phase:** 1 · Foundation files
**Who:** Brock + Claude Code
**Estimated time:** 30 minutes
**Depends on:** Tasks 02–05

## What this task does

Creates `reference/glossary.md` — the standard terms for codes, payers, statutes, and concepts used across all prompts. This file ensures consistent terminology across Skills and subagents (preventing the situation where one Skill says "EOB" and another says "Explanation of Benefits" mid-sentence).

## Prompt to paste into Claude Code

```
Create the file `reference/glossary.md` in this repository. This is the
standard terminology reference used by every Skill and subagent so the
voice stays consistent.

Structure:

# Tyndale Glossary

Intro paragraph: This file defines the standard short and long forms of
key terms used across Tyndale's intelligence layer. Skills, subagents,
and generated output use these forms consistently. When in doubt, use
the short form for chat output and the long form for formal letters.

## Code systems

| Short | Long | Context |
|---|---|---|
| CPT | Current Procedural Terminology | Procedure codes (5-digit numeric, AMA-owned) |
| HCPCS | Healthcare Common Procedure Coding System | Medicare codes (alphanumeric) |
| ICD-10 | International Classification of Diseases, 10th Revision | Diagnosis codes |
| NDC | National Drug Code | Prescription drug identifiers |
| Modifier | Modifier code | 2-character codes appended to CPT/HCPCS |

## Payers (use these exact names in output)

Tier 1 (most common):
- UnitedHealthcare (preferred to "United" or "UHC" in formal output;
  "UHC" acceptable in chat)
- Anthem
- Aetna
- Cigna
- Blue Cross Blue Shield (use specific state plan name where known —
  e.g., "Anthem Blue Cross Blue Shield of California")
- Humana
- Kaiser Permanente

Tier 2:
- Centene / Ambetter
- Molina Healthcare
- Oscar Health
- Bright Health
- Medicare (always lowercase 'm' except sentence-start)
- Medicaid (always lowercase 'm' except sentence-start)

## Statutes and regulations

| Short | Long | Citation form |
|---|---|---|
| ERISA | Employee Retirement Income Security Act | 29 U.S.C. § 1001 et seq. |
| ACA | Affordable Care Act | Patient Protection and Affordable Care Act |
| NSA | No Surprises Act | Part of Consolidated Appropriations Act, 2021 |
| MHPAEA | Mental Health Parity and Addiction Equity Act | 29 U.S.C. § 1185a |
| HIPAA | Health Insurance Portability and Accountability Act | 45 C.F.R. Parts 160 and 164 |
| IRS §501(r) | Internal Revenue Code Section 501(r) | 26 U.S.C. § 501(r) |
| EMTALA | Emergency Medical Treatment and Labor Act | 42 U.S.C. § 1395dd |
| USPSTF | U.S. Preventive Services Task Force | (referenced in ACA §2713) |

Specific frequently-cited sections:
- ACA §2713 = preventive services coverage requirement
- ACA §2719 = internal appeals and external review requirements
- ERISA §503 = claims procedure regulation
- NSA §300gg-111 = surprise billing prohibition for ER/out-of-network
- ERISA §502 = civil enforcement provisions
- IRS §501(r)(4) = financial assistance policy (FAP) requirements
- IRS §501(r)(6) = limitations on billing & collections

## Process and program names

- EOB = Explanation of Benefits (use "EOB" in chat; "Explanation of
  Benefits" first occurrence in formal letters)
- DOI = Department of Insurance (state-level)
- FAP = Financial Assistance Policy (charity care, hospital-specific)
- IDR = Independent Dispute Resolution (NSA arbitration process)
- LCD = Local Coverage Determination (Medicare)
- NCD = National Coverage Determination (Medicare)
- NCCI = National Correct Coding Initiative (bundling rules)
- MUE = Medically Unlikely Edit (CMS volume limits)
- FHIR = Fast Healthcare Interoperability Resources (data exchange standard)
- FAIR Health = FAIR Health (independent UCR database; not "Fair Health")
- HRSA = Health Resources and Services Administration
- 340B = 340B Drug Pricing Program

## Concepts (Tyndale-specific terminology)

- Case file: the central record for a user's matter; lives in Postgres
- Finding: a specific issue identified by a subagent (e.g., "bundling
  error found on CPT 12031/11402")
- Subagent: one of the five specialists (Bill Detective, Math Person,
  Legal Researcher, Strategist, Code Validator)
- Skill: a behavioral playbook stored as a directory with SKILL.md
- Collection: a Qdrant knowledge collection (one of billing_codes,
  error_detection_rules, laws_regulations, payer_policies)
- Diagnostic index: the screening checklist at the top of certain
  Skills (Bill Error Detection, Negotiation & Strategy, Charity Care)
- Lead Planner: the coordinator subagent that talks to the user
- Plan-to-memory: the pattern where the Lead Planner writes its plan to
  the case file before doing complex work, including anticipated next steps

## Voice notes

- "Insurance" or "insurer" — both acceptable; prefer "your insurer" when
  referring to the user's specific payer in chat
- "Payer" — used in formal/technical contexts (developer docs, audit logs)
- "Member" — used when referring to the insured person in formal letters
- "Patient" — used when referring to the person receiving care (often
  same as member, sometimes different — e.g., dependent of insured)
- "User" — used in product/internal contexts to refer to the Tyndale account holder

## Numbers and money

- Dollar amounts: always with $ sign, no spaces ("$4,217" not "$ 4,217" or "4217 dollars")
- Percentages: with % sign, no spaces ("20%" not "20 percent")
- Dates in chat: friendly form ("March 14, 2026" or "March 14")
- Dates in formal letters: full form ("March 14, 2026")
- Time periods: use words for short ("30 days" not "thirty days"; "180
  days" not "180 day")

Commit with message "Add Tyndale glossary".
```

## Done when

`reference/glossary.md` exists with all sections. Git log shows the commit.

## Next task

[Task 07 — Consolidate all discipline rules](07_discipline_rules.md)
