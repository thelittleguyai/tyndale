# Conformance sweep — `36_design_conformance_checklist.md` A–I

**Method:** codebase audit (file evidence), not a live browser walk — Phil does the live walk.
Strict reading: "close enough" is a FAIL. **N-A-YET** = not built, with the owning workstream.
**Date:** 2026-08-11 · first pass 24 PASS / 21 FAIL / 22 N-A-YET →
**after the conformance-fix session: 38 PASS · 7 FAIL · 1 DEFERRED · 2 PARTIAL · 22 N-A-YET** →
**after the round-2 landing port (2026-08-12): 42 PASS · 3 FAIL · 1 DEFERRED · 2 PARTIAL · 22 N-A-YET** →
**after B4 + N1 + the audit-ready email (2026-08-12): 45 PASS · 4 FAIL · 0 DEFERRED · 2 PARTIAL · 21 N-A-YET**

Rows fixed in that session are marked **PASS (2026-08-11)**. Everything still failing is either
awaiting a Brock decision, blocked on a data-model addition, or (A8) a change deliberately not
made blind — each says which.

Legend for FAILs: **[queued]** = already covered by an accepted prompt/workstream ·
**[unowned]** = no prompt covers it; needs a decision.

---

## A · Palette & design system

| # | Verdict | Evidence |
|---|---|---|
| A1 brand teal `#3E5C57` | **PASS** (2026-08-11) | adopted; `brand.teal` in design-tokens.ts, mirrors updated |
| A2 nav navy `#1D2A38` | **PASS** (2026-08-11) | adopted; `brand.navy` |
| A3 hero navy→teal gradient | **PASS** | `from-navy via-teal-deep to-teal` in the marketing hero |
| A4 money green `#2E7D5B` | **PASS** (2026-08-11) | adopted — **the 2.90:1 AA failure is fixed** (now 5.00:1) |
| A5 deductible/OOP amber | **PASS** | `amber.DEFAULT #E08A3C` + `amber.deep` used for deductible figures |
| A6 citation blue `#2C6E8F` | **PASS** (as of this session) | `colors.citation` added — required by `[B]` chip rendering |
| A7 cream bg `#FAF7F0` | **PASS** (2026-08-11) | adopted; `brand.cream` |
| A8 body ≥16px, lh 1.5 | **FAIL** [unowned] | **CORRECTION** — the earlier PASS read the MARKETING scale. Mobile body is **14px** (`type.body`). One-line change, deliberately not made blind: it reflows every screen and this session could run neither the mobile suite nor the app |
| A9 contrast ≥4.5:1 | **PASS** (2026-08-11) | 25 pairs asserted ≥4.5:1 in BOTH modes (`test_design_token_guards.py`). Fixed en route: light text.faint 3.37→4.68, warning 3.48→4.88, danger 3.84→4.72, dark text.faint 3.50→5.08 |
| A10 tap targets ≥44px | **PASS** | `min-h-[44px]` on Button/ListRow/Disclosure |
| A11 reading level / underlines | **PASS** | no decorative underlines; copy now Brock-authored |
| A12 one column | **PASS** | single-column throughout mobile; marketing stacks at all breakpoints |

## B · Landing page — round-2 port shipped 2026-08-12 (was: untouched by the redesign)

| # | Verdict | Evidence |
|---|---|---|
| B1 headline | **PASS** | exact string in `web-marketing/src/app/page.tsx` |
| B2 three-number card | **PASS** | `$2,347.18` / `$1,184.60` / `$612.40` all present, matching the app |
| B3 CTA "Check my bill" | **PASS** (2026-08-12) | now the prototype's evolved "Check my bill — free" — delta flagged for Brock |
| B4 `$504,100` savings band | **PASS** (2026-08-12) | savings band shipped; verified live on dev. **Substantiation still owed** — a public number for a pre-launch product (Brock ask #1) |
| B5 "Not a chatbot" band | **PASS** | present |
| B6 grounding two-card band | **PASS** (2026-08-12) | two proof cards (real rulebook / remembers your case), copy verbatim from the round-2 prototype |
| B7 "Our Story" small band | **PASS** (2026-08-12) | a single flex strip with the founders' portrait — deliberately not a cofounder block |
| B8 founders' story verbatim | **PASS** (2026-08-12) | prototype copy verbatim, ending "…no reason to lie to you." |
| B9 footer disclaimer | **PASS** | exact string present |
| B10 no fake urgency | **PASS** | no countdown/scarcity anywhere in source |
| B11 no "80% of bills" claim | **PASS** | not in source (a `.next/` build artifact matched "80%" — that's a Tailwind class, not copy) |

## C · Upload

| # | Verdict | Evidence |
|---|---|---|
| C1 camera-first | **PASS (web) / N-A-YET (native)** (2026-08-12) | "Take a photo of your bill" leads the upload screen; picker beside it. Web only — `expo-camera` is uninstallable while DL-44's worklets ERESOLVE stands, so native still shows the use-the-web message. No camera → no affordance (no nagging) |
| C2 checklist chips | **PASS** | Bill (required) / EOB / Insurance card chips present |
| C3 just-the-bill line | **PASS** (2026-08-11) | rendered under the upload control via `GET /v1/copy/upload` |
| C4 trust microcopy | **PASS** (2026-08-11) | lock icon + §1.2, same endpoint |
| C5 edge-detection capture | **PARTIAL** (2026-08-12) | Capture + review + retake + multi-page shipped. **Edge detection deliberately NOT built** — the guide frame is a static target; an animated tracker would be decoration posing as a capability. The readability badge is dropped for the same reason (delta B2) |
| C6 "start of your file" framing | **PASS** | `record_first_upload_frame` (§1.1) rendered by the bridge |

## D · Chat-first mechanics

| # | Verdict | Evidence |
|---|---|---|
| D1 one status card in place | **PASS** | `_upsert_status_card` — exactly one, updated (`thread_bridge.py`) |
| D2 four bars, real completion | **PASS** | `_STAGE_ORDER` + `_DONE_AT`; no percentages anywhere. **Labels now Brock's** (§2.1) |
| D3 leave-and-return line | **PASS — gated on one flag** (2026-08-12) | **The email now exists** (`app/notify/audit_ready.py`): sent on BOTH terminal outcomes (ready, and needs-documents — a user who left is waiting either way), PHI-free through the DL-47 guard, exactly-once via `audit_ready_email_sent_at`. The line is gated on `enable_audit_ready_email` — deliberately NOT the nudge flag, which is a different promise — and renders the moment an env flips it. Withheld until then, because the promise is only true where we send |
| D4 message discipline | **PASS** | bridge posts on state transitions only; status lives in the card |
| D5 ≤3 verification cards | **PASS** | `VERIFICATION_GROUP_SIZE = 3` |
| D6 Yes/No/Not sure | **PASS** | three buttons in `ThreadVerification.tsx` |
| D7 pre-select + one confirm | **PASS** | `verification_suggestion` kind; the tap commits; low-confidence → fallback |
| D8 "not sure" honored | **PASS** (2026-08-11) | answering "Not sure" posts the §4.4 acknowledgment into the thread |
| D9 cap collision Tyndale-voiced | **PASS** | `cap_collision` (§10.3) |
| D10 warn-and-continue | **PASS** | degradation paths return honest states, never hard-block |

## E · The two moments

| # | Verdict | Evidence |
|---|---|---|
| E1 reveal is a MOMENT | **PASS** | `moment_card` kind, full-width (`MomentCards.tsx`) |
| E2 three numbers stacked | **PASS** | `three_number_reveal` now Brock's three-line §6.1 block |
| E3 gap callout framing | **PASS** (2026-08-11) | on the reveal moment; suppressed at zero/negative gap (no "$0.00 less") |
| E4 finding cards + source line | **PASS** (2026-08-12) | Server stamps `FindingOut.source_line`/`has_source`; `FindingCard` RENDERS it — citation chip in citation blue when grounded, the honest no-source line when not. (Marked PASS on 08-11 in error: the server half shipped, the card never displayed it. Jest test now holds the invariant.) |
| E5 complete-and-free | **PASS** | findings complete pre-paywall; `completion` (§6.4) |
| E6 unlock card | **N-A-YET** [billing dark] | `unlock.card` key exists; no surface (enable_billing=false) |
| E7 unlock value list | **N-A-YET** [billing dark] | `unlock.value_list` + `unlock.reassurance` exist, unrendered |
| E8 subscription line | **N-A-YET** [billing dark] | `unlock.subscription` exists, unrendered |

## F · The five newer chat states

| # | Verdict | Evidence |
|---|---|---|
| F1 attest 7-option menu | **PASS** (this session) | `RELATIONSHIPS` now Brock's 7; no "self", no escape hatch; decline path built |
| F2 attest edge prompts | **PARTIAL → FAIL** [unowned] | teen + deceased authored & wired; **SUD prompt is in the checklist but NOT in his script §3** — needs his call |
| F3 illegible/partial | **PASS** (2026-08-11) | `data_quality.partial_read()` fires on the mixed case only, names the unreadable file, and discards partial figures (`never_approximate`) |
| F4 summary-vs-itemized | **PASS** (2026-08-11) | `looks_like_summary_bill()` needs evidence on both sides; harness scenario `summary_bill_only` |
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
| G6 +3d/+14d email | **PARTIAL → FAIL** [queued] | **PASS** (2026-08-17) — with a correction to this row's own earlier fix. Reading §11.5 showed his plus_3d/plus_14d are FOLLOW-THROUGH copy ("ready to make that first call"), not document-chase copy, so wiring them into the chase email — what this row previously prescribed — would have been wrong. The cron is now two nudges: the chase keeps its engineering body (it must name the missing document; email chrome per the magic-link precedent), and a new check-in nudge renders his §11.5 verbatim on its real premise (audit done + gameplan + nothing reported), +3d/+14d, email-only, deadline-aware ({deadline_date} from persisted rows only, degrading to the no-variable string when absent), suppressed once the user reports a call. Chase wins when both premises hold. Split flagged for Brock to confirm |

## H · Record, case page, resolution

| # | Verdict | Evidence |
|---|---|---|
| H1 Record → sub-case hierarchy | **PASS** | `GET /v1/record` + `/case/{id}/summary`; terminology in CLAUDE.md |
| H2 Record rows | **PASS** | provider + date + state chip (`RecordSection.tsx`) |
| H3 sub-case summary | **PASS** (2026-08-12) | findings render their source line (same mechanism as E4; corrected with it) |
| H4 case-page dark banner | **PASS** (2026-08-11) | dark moment-surface banner: deadline clock, recovered-so-far, open items **+ what each unlocks**, next check-in |
| H5 gameplan | **PASS** | `Gameplan.tsx`, biggest-wins-first ordering |
| H6 call mode | **PASS** (2026-08-12) | full-screen + XL type + step-through + the three "How did it go?" routes, and delta B4 closed the data gap the earlier PARTIAL named: `claim_number`/`account_number`/`provider_phone`/`payer_phone` are typed fields now, so the pinned strip carries the party's own identifier (claim for a payer call, account for a provider one) and tap-to-dial has a real number. Absent → the row simply doesn't render |
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
