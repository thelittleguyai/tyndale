# Tyndale BAA Tracker

Operational tracker for every Business Associate Agreement (BAA) Tyndale executes with a
vendor. Owned and maintained by Brock; updated as statuses change. This is an operational
artifact, not a technical one — but the V1-Lite critical-path chain below is a hard ship
gate.

## Posture — why these BAAs exist (read first)

Tyndale ships as a **non-HIPAA-covered consumer-health app** governed by the FTC Act, the
FTC Health Breach Notification Rule, and state privacy/health-data laws (e.g., Washington
MHMDA, California sensitive-PI) — **not** as a HIPAA covered entity or business associate.
This posture is recorded in **DL-05** and is **pending counsel's written reconfirmation
before launch**; Full V1's 1upHealth/FHIR integration triggers a HIPAA re-look at that time.

Because Tyndale is not HIPAA-covered, **these BAAs are not HIPAA-mandated.** They are
executed as **defense-in-depth and as standard vendor contract requirements**: the vendors
offer BAAs as their standard data-protection contract for sensitive data, the data Tyndale
handles is genuinely sensitive, and executing the BAA chain raises operational discipline
and contractual protection regardless of the regulatory framing. The technical discipline
(encryption, PHI scrubbing, audit log, vendor contracts) is unchanged from a covered-entity
build; only the framing differs (per DL-05). Throughout this file, "no PHI flow" is
shorthand for "no sensitive user health/billing data flow."

The security/HIPAA infrastructure itself is built by a separate contact and tracked outside
this repo's working plan (DL-11); this tracker is the operational record of the vendor
contract chain that work depends on.

## Status legend

Plain-text labels (no decorative status markers):

    Not Started    — no outreach yet
    In Progress    — initial outreach made, awaiting vendor docs
    Under Review   — docs received; Brock/counsel reviewing terms
    Executed       — signed by both parties; effective + renewal dates recorded
    Not Required   — no sensitive data flows to this vendor at this scope (defense-in-depth
                     only, or deferred to a later phase)

All rows below are owned by **Brock** and start at **Not Started** unless marked otherwise.
Cowork does not know current real-world status; Brock updates as work progresses.

## V1-Lite critical-path BAAs

> **Note (2026-06-27, per DL-79 + amended DL-49):** Claude is now called via **Azure AI
> Foundry** using **managed identity**, and the signed **Azure** BAA is taken to cover
> Claude-in-Foundry (Brock's call). The consequence for this tracker: the **Anthropic-direct
> BAA drops off the critical path** — row 1 is re-marked **Not Required** and Anthropic-direct
> is now only a **config-gated dev/emergency fallback**. The **Azure BAA (row 2) now also
> covers the Claude path.** Per amended **DL-49**, the remaining V1 BAAs to execute are
> **Azure** (incl. Claude), **AWS**, and **Voyage AI**; **1upHealth is deferred to Full V1**
> (row 4); **Stripe and SendGrid are excluded by design** (DL-49 / DL-47). DL-79 is a **dev**
> environment with no real PHI; before production go-live with real PHI, re-confirm the Azure
> BAA covers Claude-in-Foundry.

These must be **Executed** before V1-Lite launch (row 1 is now Not Required per DL-79; one
further explicit exception, row 4). Production launch is gated on this chain being complete.

| # | Vendor | Scope | Owner | Status | Effective | Renewal | Notes |
|---|--------|-------|-------|--------|-----------|---------|-------|
| 1 | Anthropic | Claude API direct — **config-gated dev/emergency fallback only** (see DL-79) | Brock | Not Required | — | annual review | **Amended per DL-79 (2026-06-27):** Claude is now called via **Azure AI Foundry** (managed identity), so the primary Claude path is covered by the **Azure BAA (row 2)** — a separate Anthropic-direct BAA is **no longer required**. Anthropic-direct is demoted to a config-gated dev/emergency fallback; if it is ever re-enabled as a production path carrying real PHI, an Anthropic BAA is required first (revert path in DL-79). |
| 2 | Microsoft Azure | Container Apps, Postgres, Blob, Key Vault, Monitor, Document Intelligence, Foundry — **incl. Claude-in-Foundry (DL-79)** | Brock | Not Started | — | annual review | Single Azure BAA covers all in-scope services on one agreement, **and now also covers Claude called via Azure AI Foundry (DL-79)** — this collapses the former Anthropic-BAA question into the Azure BAA. Document Intelligence is the V1-Lite OCR path for uploaded bills/EOBs — sensitive data flows here from day one. Highest-volume sensitive-data path (Claude + OCR both ride on this agreement). |
| 3 | AWS | Bedrock (Claude fallback path) | Brock | Not Started | — | annual review | AWS HIPAA BAA via AWS Artifact. Same sensitive-data scope as the Claude path when the Bedrock fallback is active. |
| 4 | 1upHealth | FHIR Coverage / EOB / Claim pulls | Brock | Not Required | — | annual review | **Full V1 only — defer for V1-Lite.** V1-Lite uses document upload, not FHIR pulls, so no data flows to 1upHealth at V1-Lite. Becomes a V1 critical-path BAA when the Full V1 FHIR integration ships; that integration also triggers the DL-05 HIPAA re-look. Listed here for continuity; NOT on the V1-Lite critical path. |
| 5 | SendGrid (Twilio SendGrid Email API Pro — HIPAA-eligible tier) | Account / notification email; letter-body sends at Full V1 | Brock | Not Started | — | annual review | Per DL-18, must be the **Email API Pro HIPAA-eligible tier** — SendGrid's standard tier does not include a BAA. At V1-Lite there is no letter generation/sending (per CLAUDE.md V1-Lite scope), so email carries minimal sensitive content; BAA still executed as defense-in-depth + vendor-standard, and is prerequisite to the Full V1 gated send path. |
| 6 | Voyage AI | Embeddings + reranking (knowledge retrieval) | Brock | Not Started | — | annual review | Knowledge-base corpus (statutes, code rules) is not sensitive, but user document/bill text embedded for retrieval can be. **Fallback if not signable in time: scrub-before-send** for user-bill text before it reaches Voyage. Implement the fallback in code before V1 if the BAA is not Executed. |
| 7 | FAIR Health | Cost benchmark API | Brock | Not Started | — | annual review | **Fallback if not signable in time: 3-digit ZIP precision** (HIPAA Safe Harbor de-identification) instead of full ZIP. Implement the fallback in code before V1 if the BAA is not Executed. |
| 8 | Stripe | Payment processing | Brock | Not Started | — | annual review | Defense-in-depth. Sensitive health/billing data should not flow to Stripe by design (it sees payment data only); BAA executed as a belt-and-suspenders contract. |
| 9 | Observability vendor (TBD) | Application monitoring / metrics | Brock | Not Started | — | annual review | Vendor not yet selected. Defense-in-depth — whichever vendor ends up handling app metrics. Reconfirm scope (must not ingest PHI) once selected. |

## Post-V1 BAAs

Needed before a specific later feature ships, NOT before V1-Lite:

| # | Vendor | Scope | Trigger to execute | Status | Notes |
|---|--------|-------|--------------------|--------|-------|
| 10 | Braintrust | Eval platform (production replay) | Before the V1.1 production-replay feature | Not Required | At V1, Braintrust receives only **synthetic** eval data (the `synthetic_opus47`-authored cases from `intelligence-layer/evals/synthetic/`) and hand-authored golden examples — no production PHI — so no BAA is needed yet. BAA required before any production-conversation replay lands in V1.1. |

## Not required at V1 (no sensitive-data flow)

| Vendor | Why no BAA needed | Notes |
|--------|-------------------|-------|
| OpenAI | Cross-provider fallback only on non-user-facing utility paths; no sensitive data flows by configuration | Reconfirm before any future use expansion |
| Google (Gemini) | Same as OpenAI — utility-path fallback only, no sensitive data by configuration | Reconfirm before any future use expansion |
| Qdrant Inc. | Qdrant is self-hosted inside the Azure VPC; covered by the Azure BAA (row 2) | Revisit only if Qdrant Cloud (managed) is ever adopted |

## BAA execution checklist (per vendor)

For each BAA, the owner (Brock) should:

- [ ] Initiate the request via the vendor's standard channel
- [ ] Obtain the proposed BAA text
- [ ] Review terms (or send to legal counsel for review)
- [ ] Negotiate amendments if needed
- [ ] Both parties sign
- [ ] Store the executed PDF in `intelligence-layer/operational/baa_documents/` (gitignored — confidential terms) and in Brock's off-repo secure vault
- [ ] Update this tracker: set Status = Executed, record Effective date, set Renewal date
- [ ] Add a reminder for renewal review 60 days before expiration

## Operational discipline

Tyndale policy, consistent with the security boundary in `CLAUDE.md` and the interface in
`docs/integration-contracts.md`:

- No sensitive user data flows to any vendor before that vendor's BAA is **Executed** (or, where a fallback exists — Voyage AI, FAIR Health — before the scrub/de-identification fallback is implemented in code).
- V1-Lite production launch is gated on the remaining V1-Lite critical-path BAAs (rows 2-3, 5-9) being **Executed**. Row 1 (Anthropic-direct) is **Not Required** per DL-79 — the Claude path is covered by the Azure BAA (row 2) — unless Anthropic-direct is re-enabled as a production PHI path. Row 4 (1upHealth) is excluded from the V1-Lite gate and becomes part of the gate at Full V1.
- Subprocessor-change notifications from vendors are reviewed within **30 days** of receipt; a new subprocessor handling sensitive data requires confirming BAA coverage before data flows.
- BAAs are reviewed **annually** for re-papering as standard contract terms drift.
- Voyage AI and FAIR Health fallback paths (scrub-before-send; 3-digit ZIP) must be implemented in code before V1 if their BAAs are not Executed in time.

## Renewal review process

When a BAA approaches its renewal date (60 days out):

1. Review the executed BAA against the vendor's current standard terms.
2. Confirm scope still matches current data flows.
3. Renegotiate amendments if the vendor's standard has updated.
4. Renew before expiration — never let a BAA lapse while data is flowing.

## Where executed BAAs are stored

- `intelligence-layer/operational/baa_documents/` — **gitignored**; never commit a signed BAA to the repo (the documents contain confidential contract terms).
- Brock's secure document vault — off-repo, backed up separately.

This tracker references the existence of executed BAAs; the signed documents themselves stay
off-repo.

## Status update process

Brock updates this file as statuses change. After any change:

- Update the Status label (and Effective / Renewal dates when Executed).
- Add or revise the note in the row.
- Commit with message `BAA tracker update: <vendor>`.
