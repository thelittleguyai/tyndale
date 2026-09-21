# 39 · Human Review — Admin Design (2026-09-03)

Phil → Brock · Design for the "Human Review" admin surface you proposed: every user-run case reviewable by a human — documents, conversation, analysis, results in one workspace — with approve / disapprove-with-notes, and disapprovals feeding the rules engine as **candidate** rules. Mockups: `docs/design/mockups/human_review_queue.svg` and `human_review_case.svg`.

## 0 · What already exists (this is an upgrade, not a greenfield)

The verdict spine shipped in CO-6A and is live on admin.tyndaleapp.net today: an `admin_verdicts` table (verdicts: correct / partially_correct / wrong / missed_finding / hallucinated / partial / unable_to_verify, scopeable to specific findings or a specific response), case browse with verdict filters, case detail with provenance, and verdict capture. What's missing versus your ask: the queue isn't a *worklist* (no review states or assignment), the case detail doesn't put documents + conversation + analysis side-by-side, and — the big one — **a disapproval today goes nowhere**. CO-6B (verdicts driving corrections) was designed but never built; your rule-candidate idea is a better CO-6B and this document replaces it.

## 1 · The review queue (mockup 1)

A worklist view at **Admin → Review**, one row per audited case run:

- Columns: case (provider + service line, plausibility-gated), user (masked id), run date, audit outcome (findings count + net finding $), confidence band, **review state**, assignee.
- Review states: `unreviewed → in_review → approved | disapproved` (+ `re_review` when a case re-runs after documents change — the prior verdict is kept and linked, never overwritten).
- Filters: state, verdict type, confidence band, has-system-error, date, "canary/ledgered" flag. Default sort: oldest unreviewed first.
- **Queue policy** (your call, proposed default): while volume is low, 100% of completed runs enter the queue. At scale, always-enqueue triggers — each user's first case, any `hallucinated`/`missed_finding` history for that user, low-confidence runs, system_error terminals, any canary/tripwire event, disagreement between EOB-claimed and Tyndale-computed above materiality — plus a random N% sample. The triggers are config, not code.
- Top strip: review-health stats — unreviewed count, median age, approval rate (7d/30d). The **approval rate becomes a tracked quality metric alongside the A2 eval gates** — human-review agreement is exactly the live counterpart of the judge rubric.

## 2 · The case review workspace (mockup 2)

One screen, three panes, everything a reviewer needs without leaving:

**Left — source documents.** Every uploaded document as a **file card** (type, filename, pages, characters extracted, extraction status, claim/account identifiers); click → full viewer with the OCR text toggle. This is the reviewer's ground truth.

> **SHIPPED 2026-09-21 — file card + viewer, not page thumbnails.** The viewer displays the stored image or PDF (jumping to the cited page when a citation opened it) with a **Document / OCR text** toggle; formats a browser can't render (HEIC, TIFF) say so and point at the OCR text. Two deliberate differences from the sketch above: (1) **no thumbnails** — rendering a first page needs PDF tooling the admin app doesn't have, and a thumbnail means fetching every patient document the moment a case opens, before the reviewer has asked to see any of them; (2) **every open is its own audit event** (`review_document_view`, separately for the file and for the text), in addition to the `review_view` for the case. The workspace payload itself still never carries OCR text; the viewer fetches it explicitly. Endpoints: `GET /v1/admin/review/cases/{id}/documents/{doc}` and `…/text` — reads only, no new storage of PHI.

**Center — what Tyndale did.** Three tabs:
- *Analysis*: the three numbers (billed / EOB-claimed / Tyndale-computed) exactly as the user saw them, then every finding card — type, `responsible_party`, amount, BASIS/REFERENCE codes, citations (tap to open the cited source), confidence, and the analyst notes (internal reasoning — visible here, never to users).
- *Conversation*: the full thread as the user experienced it — status cards, verification cards, chips tapped, free text, attest events. Read-only.
- *Results & journey*: what the user was told to do (gameplan steps, call script, identifiers used), disclosure-tier renderings, and any recorded outcomes (call outcomes, recovered money, feedback).

**Right — the verdict panel.** This is where your ask lands:

- **Approve** — one click, optional note. Writes an `approved` verdict; case leaves the queue.
- **Disapprove** — requires: (a) a verdict type from the existing enum (wrong / missed_finding / hallucinated / partially_correct / unable_to_verify), (b) scope — whole case or specific finding(s), click-to-select on the center pane, (c) a structured note: *what was wrong* and *what the correct analysis is*.
- Verdicts are append-only (matches the existing model — a case can carry many), stamped with the admin's UUID (per the security review convention), and written to the encrypted audit log like every admin action.

## 3 · Disapproval → rule candidate (the new pipeline, and the part I want your eyes on)

When a reviewer disapproves with a correction, the panel offers **"Draft a rule from this"**:

- Pre-fills a **rule candidate** in your own `error_detection_rules` schema — `rule_class` (provider_coding / payer_adjudication / legal_protection / pricing), `rule_type`, `responsible_party`, `applicable_codes` where relevant, plus the case's specifics generalized into a description and the correction as the expected behavior. The reviewer edits before saving.
- Candidate lifecycle: `draft → pending_author → authored → ingested`, in a new **Rule candidates** tab on the same Review section. **Nothing auto-activates — ever.** A candidate is an *input to your authoring queue*, in your schema, with the source case linked as evidence. You (content owner) approve/rewrite it like any tranche entry; ingestion then follows the exact same validated path Tranche 2 uses. This keeps the doctrine intact: rules are authored content with an owner, never machine-accumulated — the review UI just does the paperwork of turning a caught mistake into a well-formed draft.
- Every candidate also generates an **eval-scenario stub** (the case shape + the expected correct outcome, synthetic-ified) so each human catch can permanently join the regression corpus. This is the flywheel: mistake → rule candidate → your authorship → detection improves → eval locks it in.
- PHI boundary: the candidate stores the generalized rule + a case *reference*, never patient data in the rule text; a lint on save blocks names/DOBs/account numbers in candidate fields (same plausibility/furniture machinery, reused).

## 4 · Access, privacy, audit

Admin-only behind the existing IP allowlist + admin auth; every view of a case in review is itself an audit-log event (reviewer UUID, case, timestamp) — reviewing PHI is an access that must be accountable; notes fields carry a "no patient identifiers needed here" hint (the case link carries context); the queue shows masked user ids, full identity only inside the case workspace.

## 5 · Phasing & effort (honest estimates)

- **Phase 1 (~2 sessions):** queue with review states + the three-pane workspace assembled from existing pieces (documents API, thread projection, findings — all exist) + approve/disapprove wired to the existing verdict model.
- **Phase 2 (~1–2 sessions):** rule-candidate pipeline + candidates tab + eval-stub generation + PHI lint.
- **Phase 3 (later, with real volume):** assignment/multi-reviewer, queue triggers config UI, approval-rate trend on the analytics dashboard, CO-6B-style user-facing corrections for approved adjustments (needs its own design pass — telling a user "we corrected your audit" is a copy + trust surface that's yours).

## 7 · DECISIONS — Brock 2026-09-17 (design APPROVED; these amend §1–§6 and govern the build)

- **2a · Provenance, both surfaces.** (i) Per-finding "why" expander under each finding card: inputs used (source chips) · rule applied + effective date · computation · confidence — five lines. (ii) A fourth center tab **"Data & provenance"**: complete inventory by origin — user documents (value · page/line · extraction confidence) · user answers/attestations (timestamped) · connected-API pulls (resource, fetched-when, as-of) · knowledge chunks retrieved and cited (collection, effective date, last-verified) · pricing/reference data (source, as-of) · priors applied (value, tier, resulting range) · live lookups (NPPES, LEIE, reviews — timestamped). Plus two sections: **Missing** (inputs wanted, not obtained, how it degraded) and **Retrieval misses** (rules in the corpus not retrieved, or retrieved and not applied) — this separates content gaps (Brock's) from reasoning errors (engineering's) without manual diagnosis.
- **2b · Disapproval required fields.** Verdict type (existing enum) · scope · **cause** (one, required): `content_gap` | `reasoning_error` | `bad_input` | `stale_data_source` · structured note: what Tyndale concluded → what it should have → which input/rule was the problem. **Cause routes the fix:** content_gap → rule candidate (authoring queue) · reasoning_error → engineering ticket with the provenance snapshot attached · bad_input → extraction/OCR fix (ticket if systemic, data correction if one-off) · stale_data_source → data-ops item. **Every disapproval generates the eval-scenario stub regardless of cause.**
- **2c · Three-way verdict.** Approve · Disapprove · **Can't verify**. `unable_to_verify` is its own top-level action and is **excluded from the approval-rate denominator**. The other six enum values live under Disapprove.
- **2d · Queue policy.** 100% of completed runs by default, with a random-sample percentage dial the reviewer can turn down; always-enqueue triggers (first case, low confidence, system errors, canary events, above-materiality disagreement) fire regardless of the dial. Triggers are config.
- **2e · Reviewers.** Brock and Phil only at launch; no assignment machinery in Phase 1; reviewer UUID on every verdict. Cowork triages and drafts candidates but is not an approver — a human looks.
- **2f · User-facing corrections (Phase 3 ruling, design toward it now).** When a disapproval changes a user's answer, the corrected answer posts into the user's thread as a NEW Tyndale message on next open ("I need to correct something…"), with the original left in place and marked **corrected**. Append-only, never a silent edit. Copy is Brock's (including the bad-news variant). Thread must support a "corrected" marker on a prior message + a linked follow-up.
- **2g · Mockups.** Layout and vocabulary approved; verdict panel becomes three actions; center pane gains the fourth tab (mockup updated 2026-09-18).

## 6 · Open questions for you (ANSWERED 2026-09-17 — see §7; retained for the record)

1. **Queue policy** — 100%-review to start, then the trigger set in §1? Or sampled from day one?
2. **Verdict vocabulary** — keep the shipped 7-value enum under Approve/Disapprove, or do you want a different reviewer-facing taxonomy? (UI language is yours; the enum is load-bearing in the DB.)
3. **Who reviews** — just you + Phil at launch, or do we need roles/assignment in Phase 1?
4. **User-facing corrections** — when a disapproval changes a user's answer, what (if anything) does the user hear, and in whose words? Phase 3 needs your ruling before we build it.
5. Mockups attached — layout/vocabulary reactions welcome; the palette and components are the shipped admin system, nothing new.
