# Conformance sweep — `36_design_conformance_checklist.md` A–I

**Method:** codebase audit (file evidence), not a live browser walk — Phil does the live walk.
Strict reading: "close enough" is a FAIL. **N-A-YET** = not built, with the owning workstream.
**Date:** 2026-08-11 · **Total:** 24 PASS · 21 FAIL · 22 N-A-YET

Legend for FAILs: **[queued]** = already covered by an accepted prompt/workstream ·
**[unowned]** = no prompt covers it; needs a decision.

---

## A · Palette & design system

| # | Verdict | Evidence |
|---|---|---|
| A1 brand teal `#3E5C57` | **FAIL** [queued] | ships `#1F4E4A` (`design-tokens.ts:19`). Pending Brock — `palette_reconciliation.md` |
| A2 nav navy `#1D2A38` | **FAIL** [queued] | ships `#0E1F2B` (`design-tokens.ts:14`). Same doc |
| A3 hero navy→teal gradient | **PASS** | `from-navy via-teal-deep to-teal` in the marketing hero |
| A4 money green `#2E7D5B` | **FAIL** [queued] | ships `sage #3DAA7E` — **and it fails AA at 2.90:1**. Adopting Brock's fixes it |
| A5 deductible/OOP amber | **PASS** | `amber.DEFAULT #E08A3C` + `amber.deep` used for deductible figures |
| A6 citation blue `#2C6E8F` | **PASS** (as of this session) | `colors.citation` added — required by `[B]` chip rendering |
| A7 cream bg `#FAF7F0` | **FAIL** [queued] | ships `#F5F1EA`. Same doc |
| A8 body ≥16px, lh 1.5 | **PASS** | mobile type scale base 16 / lh 1.5; marketing `text-base` = 1rem/1.5rem |
| A9 contrast ≥4.5:1 | **FAIL** [unowned] | `sage #3DAA7E` money figures at **2.90:1**; `text.faint` at AA-large only (RD-4 note) |
| A10 tap targets ≥44px | **PASS** | `min-h-[44px]` on Button/ListRow/Disclosure |
| A11 reading level / underlines | **PASS** | no decorative underlines; copy now Brock-authored |
| A12 one column | **PASS** | single-column throughout mobile; marketing stacks at all breakpoints |

## B · Landing page — **marketing site untouched by the redesign**

| # | Verdict | Evidence |
|---|---|---|
| B1 headline | **PASS** | exact string in `web-marketing/src/app/page.tsx` |
| B2 three-number card | **PASS** | `$2,347.18` / `$1,184.60` / `$612.40` all present, matching the app |
| B3 CTA "Check my bill" | **PASS** | present |
| B4 `$504,100` savings band | **FAIL** [unowned] | figure absent from source |
| B5 "Not a chatbot" band | **PASS** | present |
| B6 grounding two-card band | **FAIL** [unowned] | no two-card grounding treatment in `page.tsx` |
| B7 "Our Story" small band | **FAIL** [unowned] | no "Our Story" band at all |
| B8 founders' story verbatim | **FAIL** [unowned] | absent (blocked on B7) |
| B9 footer disclaimer | **PASS** | exact string present |
| B10 no fake urgency | **PASS** | no countdown/scarcity anywhere in source |
| B11 no "80% of bills" claim | **PASS** | not in source (a `.next/` build artifact matched "80%" — that's a Tailwind class, not copy) |

## C · Upload

| # | Verdict | Evidence |
|---|---|---|
| C1 camera-first | **FAIL** [queued — prompt names it] | `upload.tsx` is a file picker; no "Snap a photo" primary |
| C2 checklist chips | **PASS** | Bill (required) / EOB / Insurance card chips present |
| C3 just-the-bill line | **FAIL** [unowned] | key `upload_just_the_bill` now EXISTS (§1.3) but no surface renders it |
| C4 trust microcopy | **FAIL** [unowned] | key `upload_trust_microcopy` now EXISTS (§1.2) but no surface renders it |
| C5 edge-detection capture | **N-A-YET** | camera capture not built (same workstream as C1) |
| C6 "start of your file" framing | **PASS** | `record_first_upload_frame` (§1.1) rendered by the bridge |

## D · Chat-first mechanics

| # | Verdict | Evidence |
|---|---|---|
| D1 one status card in place | **PASS** | `_upsert_status_card` — exactly one, updated (`thread_bridge.py`) |
| D2 four bars, real completion | **PASS** | `_STAGE_ORDER` + `_DONE_AT`; no percentages anywhere. **Labels now Brock's** (§2.1) |
| D3 leave-and-return line | **FAIL** [unowned] | key `status_leave_and_return` now EXISTS (§2.2) but the card doesn't render it |
| D4 message discipline | **PASS** | bridge posts on state transitions only; status lives in the card |
| D5 ≤3 verification cards | **PASS** | `VERIFICATION_GROUP_SIZE = 3` |
| D6 Yes/No/Not sure | **PASS** | three buttons in `ThreadVerification.tsx` |
| D7 pre-select + one confirm | **PASS** | `verification_suggestion` kind; the tap commits; low-confidence → fallback |
| D8 "not sure" honored | **FAIL** [unowned] | engine honors it, but §4.4's copy (`verification_not_sure`) isn't rendered |
| D9 cap collision Tyndale-voiced | **PASS** | `cap_collision` (§10.3) |
| D10 warn-and-continue | **PASS** | degradation paths return honest states, never hard-block |

## E · The two moments

| # | Verdict | Evidence |
|---|---|---|
| E1 reveal is a MOMENT | **PASS** | `moment_card` kind, full-width (`MomentCards.tsx`) |
| E2 three numbers stacked | **PASS** | `three_number_reveal` now Brock's three-line §6.1 block |
| E3 gap callout framing | **FAIL** [unowned] | no "$572.20 less than your insurer's number" framing |
| E4 finding cards + source line | **PARTIAL → FAIL** | title/amount/severity present in `FindingCard.tsx`; **source line not rendered** though `finding_card_source` (§6.3) now exists |
| E5 complete-and-free | **PASS** | findings complete pre-paywall; `completion` (§6.4) |
| E6 unlock card | **N-A-YET** [billing dark] | `unlock.card` key exists; no surface (enable_billing=false) |
| E7 unlock value list | **N-A-YET** [billing dark] | `unlock.value_list` + `unlock.reassurance` exist, unrendered |
| E8 subscription line | **N-A-YET** [billing dark] | `unlock.subscription` exists, unrendered |

## F · The five newer chat states

| # | Verdict | Evidence |
|---|---|---|
| F1 attest 7-option menu | **PASS** (this session) | `RELATIONSHIPS` now Brock's 7; no "self", no escape hatch; decline path built |
| F2 attest edge prompts | **PARTIAL → FAIL** [unowned] | teen + deceased authored & wired; **SUD prompt is in the checklist but NOT in his script §3** — needs his call |
| F3 illegible/partial | **FAIL** [unowned] | `dataquality_partial_illegible` (§5.1) exists and is the degradation target, but no extraction path detects "partially illegible" and renders it |
| F4 summary-vs-itemized | **FAIL** [unowned] | `dataquality_summary_not_itemized` (§5.2) exists; classifier doesn't distinguish summary vs itemized |
| F5 wrong document typed | **PASS** | 4-branch router + §5.3 copy naming `{detected_doc_type}` |
| F6 reconcile-first ladder | **PASS** | state machine; last-resort gated (`reconcile.py`) |
| F7 fabrication decline | **PASS** | §10.1 + truthful reframe |
| F8 guarantee decline | **PARTIAL → FAIL** [unowned] | wired + no-prediction contract enforced, but §10.2 **requires a cited base rate we don't have**, so it degrades. Needs a no-base-rate variant from Brock |
| F9 PACE handoff | **PASS** | §12.1, case stays open |

## G · Orchestration rendering

| # | Verdict | Evidence |
|---|---|---|
| G1 verbatim | **PASS** | `test_script_drift.py` fails CI on any drift, naming the key |
| G2 variables / missing → §5 | **PASS** | single-brace interpolation; unfilled slot → §5.1 degradation + counter |
| G3 `[B]` with citation chip | **PARTIAL → FAIL** [unowned] | renderer enforces it and `citation` colour now exists, but **zero keys are tagged `[B]`** — his 4 `[B]` marks are dual `[A]/[B]` on §6.3/§12.1, which we render `[A]`. Needs his call |
| G4 `[C]` no prediction | **PASS** | 5 `[C]` keys; load-time assert + forbidden-language test |
| G5 close-the-loop | **PASS** | X1 contract in CI; §8.3 close line authored |
| G6 +3d/+14d email | **PARTIAL → FAIL** [queued] | cadence + scan built; `nudge.plus_3d`/`plus_14d` (§11.5) now exist but the cron sends its own text and `enable_nudge_emails=false` |

## H · Record, case page, resolution

| # | Verdict | Evidence |
|---|---|---|
| H1 Record → sub-case hierarchy | **PASS** | `GET /v1/record` + `/case/{id}/summary`; terminology in CLAUDE.md |
| H2 Record rows | **PASS** | provider + date + state chip (`RecordSection.tsx`) |
| H3 sub-case summary | **PARTIAL → FAIL** [unowned] | three numbers + status + "continue the conversation" present; **findings lack citations** (same gap as E4) |
| H4 case-page dark banner | **FAIL** [unowned] | no deadline clock / recovered-so-far / next-check-in banner |
| H5 gameplan | **PASS** | `Gameplan.tsx`, biggest-wins-first ordering |
| H6 call mode | **PARTIAL → FAIL** [unowned] | step-through + "How did it go?" 3 routes present; **no tap-to-dial, no pinned claim#/dollar strip, not full-screen XL** |
| H7 pushback route | **PASS** | `call_mode.pushback` (§9.5) — steadfast framing |
| H8 continuous journey | **PASS** | §11.1 beat + `record_identity` (§11.2) authored |
| H9 needs-something checklist | **PASS** | ☑/☐ card + how-to-get + inline add-document + §8.3 close |

## I · Entitlements — **pricing rework**

| # | Verdict | Evidence |
|---|---|---|
| I1 $4.99 includes follow-through | **N-A-YET** | billing dark |
| I2 subscription gates count, never mid-case | **N-A-YET** | billing dark |
| I3 free tier = audit complete | **N-A-YET** | billing dark |

---

## The ❌ list, sorted for Brock

**Already owned (no decision needed):** A1/A2/A4/A7 (palette — his call pending) ·
C1/C5 (camera-first) · E6–E8 + I1–I3 (billing dark) · G6 (email wiring).

**Needs a decision — genuinely unowned (13):**

1. **A9 / A4 contrast** — money figures at 2.90:1 ship *today*. Accessibility, not taste.
2. **B4, B6, B7, B8** — savings band, grounding band, Our Story band + copy: the marketing
   site never got the redesign pass. Four items, one workstream.
3. **C3, C4, D3, D8** — four authored strings now in the registry with **no surface rendering
   them**. Cheap to wire; needs a home.
4. **E3, E4/H3** — gap callout, and the **source line on finding cards** (E4 is a grounding-
   doctrine item, not cosmetic).
5. **F2** — his checklist says SUD edge prompt; his script doesn't author one. Contradiction.
6. **F3, F4** — §5.1/§5.2 copy exists; no detection wires to it.
7. **F8** — §10.2 needs a no-cited-base-rate variant or it degrades at launch.
8. **G3** — no key is tagged `[B]`; his dual `[A]/[B]` marks need resolving per-key.
9. **H4, H6** — case-page banner; call mode's tap-to-dial + pinned strip + full-screen.
