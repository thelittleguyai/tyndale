# Task 31 — Build the BAA tracker

**Phase:** 7 · Documentation
**Who:** Brock + Claude Code
**Estimated time:** 45 minutes
**Depends on:** All previous phases

## What this task does

Creates the BAA (Business Associate Agreement) tracker — a spreadsheet-ready document for tracking all 12 BAAs that must be executed before V1 launch. This is operational, not technical, but it's a hard ship gate.

## Prompt to paste into Claude Code

```
Create `operational/baa_tracker.md` with a comprehensive BAA tracking
document.

Structure:

# Tyndale BAA Tracker

This document tracks every Business Associate Agreement Tyndale needs
to execute. HIPAA requires that PHI flows only to vendors with whom we
have an executed BAA. Production launch is gated on the full BAA chain
being in place.

## Status legend

- 🔴 Not started
- 🟡 In progress (initial outreach made, awaiting docs)
- 🟠 Under review (received docs, legal/Brock reviewing)
- 🟢 Executed (signed by both parties)
- ⚫ Not required (defense-in-depth only; no PHI flow currently)

## V1 critical-path BAAs

These must be 🟢 before V1 launch:

| # | Vendor | Scope | Owner | Status | Effective | Renewal | Notes |
|---|--------|-------|-------|--------|-----------|---------|-------|
| 1 | Anthropic | Claude API direct (Lead Planner, all subagents, Skills) | Brock | 🔴 | — | annual | Request HIPAA-ready Enterprise BAA directly from Anthropic sales |
| 2 | Microsoft Azure | Container Apps, Postgres, Blob, Key Vault, Monitor, Document Intelligence, Foundry | Brock | 🔴 | — | annual | Azure BAA covers all in-scope services on a single agreement |
| 3 | AWS | Bedrock (Claude fallback path) | Brock | 🔴 | — | annual | AWS HIPAA BAA via AWS Artifact |
| 4 | 1upHealth | FHIR Coverage/EOB/Claim pulls | Brock | 🔴 | — | annual | Negotiated as part of 1upHealth platform agreement |
| 5 | Postmark | Email sends with PHI in letter bodies | Brock | 🔴 | — | annual | Postmark "Healthcare" tier required (standard tier doesn't include BAA) |
| 6 | Voyage AI (via MongoDB) | Embeddings + reranking | Brock | 🔴 | — | annual | If not signable in time, implement scrub-before-send for user-bill text |
| 7 | FAIR Health | Cost benchmark API | Brock | 🔴 | — | annual | If not signable in time, use 3-digit ZIP precision (HIPAA Safe Harbor) |
| 8 | Stripe | Payment processing (defense-in-depth) | Brock | 🔴 | — | annual | PHI shouldn't flow to Stripe by design, but BAA is defense-in-depth |
| 9 | Observability vendor | Application monitoring (defense-in-depth) | Brock | 🔴 | — | annual | Vendor TBD; whichever ends up handling app metrics |

## Post-V1 BAAs

These are needed before specific features ship but NOT before V1:

| # | Vendor | Scope | Trigger to execute | Status | Notes |
|---|--------|-------|--------------------|--------|-------|
| 10 | Braintrust | Eval platform (production replay) | Before V1.1 production replay feature | 🔴 | At V1, Braintrust receives only synthetic data; no BAA needed |

## Not required at V1 (no PHI flow)

| Vendor | Why no BAA needed | Notes |
|--------|---------|-------|
| OpenAI | Cross-provider fallback only on non-user-facing utility paths; no PHI flows by configuration | Reconfirm before any future use expansion |
| Google (Gemini) | Same as OpenAI | Reconfirm before any future use expansion |
| Qdrant Inc. | Qdrant is self-hosted in Azure VPC; covered by Azure BAA | Will revisit if Qdrant Cloud becomes HIPAA-attested |

## BAA execution checklist (per vendor)

For each BAA the owner should:

- [ ] Initiate request via vendor's standard channel
- [ ] Obtain proposed BAA text
- [ ] Review terms (or send to legal counsel for review)
- [ ] Negotiate amendments if needed
- [ ] Both parties sign
- [ ] Store executed PDF in `operational/baa_documents/` (gitignored —
      contains confidential terms)
- [ ] Update this tracker with effective date and renewal date
- [ ] Add reminder for renewal review 60 days before expiration

## Operational discipline

Per decision D19:

- No PHI flows to any vendor before that vendor's BAA is 🟢
- Production launch gated on entire critical-path list being 🟢
- Subprocessor change notifications from vendors must be reviewed
  within 30 days of receipt
- BAAs reviewed annually for re-papering as standard contract terms drift
- Voyage AI and FAIR Health have fallback paths if BAA isn't signable
  in time — those fallback paths must be implemented in code before V1

## Renewal review process

When a BAA approaches its renewal date (60 days out):
1. Review the executed BAA against current standard terms
2. Confirm scope still matches current data flows
3. Renegotiate amendments if vendor's standard has updated
4. Renew before expiration; never let a BAA lapse

## Where executed BAAs are stored

The executed PDF documents are stored in:
- `operational/baa_documents/` (gitignored)
- Brock's secure document vault (off-repo, backed up separately)

Never commit a signed BAA to the repo. The tracker references their
existence but the documents themselves stay off-repo.

## Status update process

This document is updated by Brock as BAA statuses change. After any
change:
- Update the status emoji
- Add a note in the row
- Commit with message "BAA tracker update: <vendor>"

Commit with message "Add BAA tracker".
```

## Done when

`operational/baa_tracker.md` exists with the full BAA tracking table. Git log shows the commit.

## Next task

[Task 32 — Engineering handoff brief](32_handoff_brief.md)
