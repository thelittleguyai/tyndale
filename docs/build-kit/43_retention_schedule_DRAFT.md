# 43 · Retention schedule — plan-year rule for EOBs (DRAFT)

**Status: DRAFT for counsel.** Engineering write-up of Brock's decision 9 (2026-09-21,
`brock_to_phil_guided_intake_answers_2026-09-21.md`). **No purge code exists** and none is built
in Phase 1–2: this file is the schedule the scheduler will implement. Two gates are separate
(both on `GO_LIVE_CHECKLIST.md`):

| gate | launch-gating? |
|---|---|
| This schedule, documented and signed off by counsel | **yes** |
| The scheduler that executes it | **no** — it must exist before the first purge date, which is more than a year after launch; built as A3, in sequence |

## The rule (decision 9)

> Retain a plan year's EOBs through the end of that plan year plus the locked post-closure tail
> (6–12 months, long enough to close any case that straddles the boundary), then purge.

1. **What it covers.** Every EOB-family document a case holds (`eob`, `ma_eob`, `msn`,
   `tricare_eob` — `app/intake/timeline.EOB_DOC_TYPES`) and the structured `case_files.eobs`
   entries read from them. doc 40 §B item 13: a year of EOBs is far more PHI than one bill, so the
   schedule applies to the timeline's documents, not only to the bill being checked.
2. **The anchor is the PLAN year, not the calendar year.** Many plans do not start January 1, and
   deductibles and out-of-pocket reset at the plan-year boundary, which is what makes an EOB
   load-bearing. The anchor is the start the SBC's own "Coverage Period" states. When no SBC is
   on file, the anchor is the member's answer to the plan-year ask. Both are persisted on the
   case's coverage record as `coverage.plan_year_start` (ISO date) with
   `coverage.plan_year_start_source` = `sbc` | `user`. The record is written by the intake
   planner on every step and by every upload, so the anchor outlives the intake snapshot
   (`app/intake/timeline.persist_plan_year_start`). The SBC wins over the answer when both exist.
3. **Retain through the end of that plan year** — `plan_year_start` + 1 year − 1 day, for the
   plan year the EOB's date of service falls in.
4. **Plus the post-closure tail**, 6–12 months: long enough to close any case that straddles
   the boundary (an audit whose EOBs sit in two plan years). **The exact value is Brock's +
   counsel's to set** — it is "locked" as a range in decision 9, not as a number.
5. **Then purge.** See "What purge means" — an open item for counsel.
6. **It sits INSIDE B5-6, it does not replace it.** A verified patient deletion request is still
   honored immediately, whatever this schedule says (Brock's locked rules-logic item B5-6; the
   source decision file is not in this repo — decision 9 restates the part that matters here).

## What the scheduler will read (all persisted today)

| input | where |
|---|---|
| the EOB documents, their types and stored files | `case_files.documents[]` (`document_type`, `uri`) |
| each EOB's date of service | the entry's `date_of_service` (read from the text at upload) or the structured `case_files.eobs[]` entry — the timeline rows already join the two (`app/intake/timeline.eob_rows`) |
| the plan-year anchor + its source | `case_files.coverage.plan_year_start` / `plan_year_start_source` |
| the case's closure | `case_files.status` / `updated_at` (resolved / archived / complete) |

## Open for counsel / Brock (none of these is decided here)

- **No anchor at all** (no SBC, no answer). Proposed default, for review: never purge EOBs earlier
  than 12 months after the latest EOB date of service on the case plus the tail. That is the
  longest a plan year containing that EOB could still be open, and it never under-retains.
- **The tail's exact length** within 6–12 months.
- **An EOB with no readable date of service.** No per-document upload timestamp is stored today,
  so such an EOB has no date to anchor on. Proposed: treat it as belonging to the latest plan
  year on the case (never under-retain), and add an upload timestamp to new entries when A3 is
  built.
- **What purge means**: the uploaded file (Azure Blob), its stored OCR text and extracted fields,
  the structured `eobs` entries, and anything derived that still identifies the member.
  De-identified improvement data under the two-consent model is a separate question.
- **The bill and the audit's findings.** Decision 9 is about EOBs. Whether the bill, the findings
  and the case thread follow the same plan-year clock is not decided.
- **Other statements that must agree** with this schedule once signed: the privacy policy §10
  (`docs/tyndale-spec/02_privacy_policy.md`, "while your account is active … then as required")
  and SECURITY_GO_LIVE MEDIUM-13 (account deletion vs retained case-file PHI). The 7-year
  retention in `integration-contracts.md` is the audit-EVENT log, a different record.
