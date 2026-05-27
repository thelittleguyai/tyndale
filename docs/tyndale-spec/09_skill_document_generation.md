# Task 09 — Build the Document Generation Skill

**Phase:** 2 · Skill scaffolding
**Who:** Brock + Claude Code
**Estimated time:** 2–3 hours
**Depends on:** Tasks 01–08

## What this task does

Builds the Document Generation Skill — the playbook for writing all 21 letter types Tyndale generates. Includes few-shot examples per letter type (which the research showed beats prose instructions for complex outputs).

## Prompt to paste into Claude Code

```
Create the Document Generation Skill in this repository.

Directory structure:

skills/document_generation/
├── SKILL.md
├── _shared/
│   ├── tone_guide.md
│   ├── citation_handling.md
│   └── readability_check.md
└── letter_types/
    ├── 01_internal_appeal.md
    ├── 02_external_review_request.md
    ├── 03_nsa_open_negotiation.md
    ├── 04_nsa_idr_initiation.md
    ├── 05_doi_complaint.md
    ├── 06_charity_care_application.md
    ├── 07_charity_care_appeal.md
    ├── 08_balance_bill_dispute.md
    ├── 09_payment_plan_request.md
    ├── 10_itemized_bill_request.md
    ├── 11_medical_records_request.md
    ├── 12_prior_auth_appeal.md
    ├── 13_coverage_determination_appeal.md
    ├── 14_eob_clarification_request.md
    ├── 15_provider_negotiation.md
    ├── 16_collections_dispute.md
    ├── 17_credit_report_dispute.md
    ├── 18_emergency_appeal_expedited.md
    ├── 19_mental_health_parity_appeal.md
    ├── 20_preventive_coverage_appeal.md
    └── 21_re_adjudication_request.md

For SKILL.md:

YAML frontmatter:
- name: document_generation
- description: "a little pushy" description. Cover: drafts all 21 letter
  types Tyndale generates including appeals, complaints, dispute
  letters, and applications. When to use (any time Tyndale needs to
  produce a formal written document). When NOT to use (chat responses,
  internal logging). The hard rule that numeric values, dollar amounts,
  codes, dates, and named entities are NEVER invented — they come from
  structured inputs only.
- version: 1.0.0

Body (under 500 lines):
- Brief intro to the Skill's role
- References to reference/principles.md, reference/voice_tiering.md,
  reference/citations.md, reference/glossary.md
- Hard rules section:
  * Every numeric value must trace to a structured input (Tier A discipline)
  * Every legal claim must have a citation (Tier B discipline)
  * Outcome predictions forbidden (Tier C discipline)
  * Plain-language summary required at the top of every formal letter
    aimed at the user (so they can review before signing)
  * Readability check: target 8th-grade reading level for the
    plain-language summary; legal/formal sections can be higher
- Index of the 21 letter types with one-line description of each
- Reference to _shared/ files for cross-cutting tone, citation, readability guidance

For _shared/tone_guide.md:
- Formal letters use the confident-advocate voice from voice_tiering.md
- Address recipients formally (Dear UnitedHealthcare Appeals Department,)
- First paragraph states the request clearly
- Body paragraphs present the case with citations
- Closing paragraph requests specific action with a deadline
- Signature block matches the user's account info

For _shared/citation_handling.md:
- All legal claims use the inline format from reference/citations.md
- Formal letters include a References section at the bottom listing all
  cited authorities with their full names
- Anthropic's Citations feature output is the source of truth; transform
  to letter-appropriate format for the user-facing rendering

For _shared/readability_check.md:
- Every generated letter has TWO sections: a plain-language summary
  (8th-grade reading level, no jargon) at the top for the user, and the
  formal letter body below
- The user reviews the plain-language summary before clicking Send
- The plain-language summary explains: what the letter says, what
  they're asking for, what happens next, what the user needs to do
  (usually nothing — Tyndale handles follow-up)

For each of the 21 letter type files in letter_types/:

Don't write comprehensive letter templates yet — the domain expert work
fills those in. For now, scaffold each file with:

- Title (the letter type)
- Frontmatter:
  * letter_type: the name
  * applicable_situations: when this letter type is used
  * typical_recipient: who it's sent to
  * typical_relevant_authorities: which laws/regulations typically cited
  * typical_resolution_window: how long it usually takes to hear back
- A "When to use this letter type" section (2-3 sentences)
- A "Structural skeleton" section with placeholder text for each
  paragraph (e.g., "Paragraph 1 — state the request: [appellant requests
  re-adjudication of claim {claim_id} dated {date_of_service}]...")
- A "Required structured inputs" section listing every variable the
  letter draws from (e.g., claim_id, date_of_service, billed_amount,
  allowed_amount, member_id, etc.)
- A "Citations typically required" section listing the legal authorities
  that typically appear in this letter type
- A "Few-shot example" placeholder — a comment saying "Add 2–3 real
  example letters here once Brock and the contracted attorney author them"

About 40-60 lines per letter type file.

After creating all files, commit with message
"Add Document Generation Skill with 21 letter type scaffolds".
```

## Done when

- `skills/document_generation/SKILL.md` exists with proper frontmatter and hard rules
- `_shared/` has tone_guide, citation_handling, readability_check files
- All 21 letter type files exist in `letter_types/` with proper structure
- Each letter type file has the structural skeleton with placeholder variables
- Git log shows the commit

## Next task

[Task 10 — Build the Negotiation & Strategy Skill](10_skill_negotiation_strategy.md)
