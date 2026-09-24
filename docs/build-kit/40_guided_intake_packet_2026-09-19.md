# 40 · Guided Intake — Design Packet for the Simplified Version

Brock → Phil · 2026-09-19 · Companion to the 18 ChatGPT concept screens (attached separately — NOT yet in this repo; see engineering note). Filed to build-kit 2026-09-21 by Cowork; canonical source for the guided-intake sessions.

> **Engineering note (2026-09-21).** This packet lands on top of an existing guided wizard: Phase CO-1A (May) built `/intake/*` — twelve screens (`welcome · bills · eobs · insurance-card · benefits · deductible · oop-max · coverage-details · coverage-regime-confirm · visit-context · plan-proposal · complete`), server-side step tracking (`routes/intake.py`: `_next_step`, `_missing_items`, `_apply_regime_detection`), the guided-answers → coverage persistence, the summary-bill heuristic, and the all-plan-year-EOBs completeness signal (`test_guided_flows.py`). CO-1A's fixed `_next_step` sequence is exactly what §A4 says must not exist — it becomes the Intake Planner. Its screen copy is engineering-voiced (no registry keys) — that becomes `intake.*` keys under §A6. Phase 1 build plan + open decisions: `claude_code_prompt_guided_intake_p1_2026-09-21.md` (workspace root) and `reply_to_brock_2026-09-21_guided_intake.md`.
>
> ~~Referenced research files not present in this repo as of filing.~~ **Received 2026-09-24** (attached by Brock): now at `docs/research/example_documents_sources_2026-09-17.md`, `docs/research/portal_navigation_guide_2026-07-02.md`, `docs/research/tyndale_oop_calculation_method.md`; plus `41_example_illustrations_spec.md` (this folder) and the 18 concept screens (`docs/design/concept-screens/`, images to be dropped).
>
> **DECISIONS — Brock 2026-09-21 (`brock_to_phil_guided_intake_answers_2026-09-21.md`), three changed from this packet:**
> 1. **Guided is the ONLY front door** (changed from "run both"): cohort 100% guided; freeform chat + quick-actions grid hidden; cases, settings, Record, post-unlock chat kept; chat-first stays behind `intake_mode`, never deleted; `intake_mode` recorded on every case.
> 2. Fifth-grade rule: ratchet — new `intake.*` strict, existing 136 keys report-only until touched.
> 3. A9 scanning explicitly supersedes N1/B2 — Phase 4, costed as its own phase; native capture parked on DL-44.
> 4. Paywall: unlock moment renders with the honest beta line and proceeds — **temporary, tracked as a launch-checklist item**; paywall goes live when billing lands.
> 5. Files attached (received); Brock wants the absolute path of the directory we sync from.
> 6. **Email forwarding DROPPED** (changed): remove from the timeline entirely; upload-fed. Revisit only via a security packet.
> 7. Link expiry: real 15 minutes; resume must re-issue a fresh link cleanly.
> 8. Illustrations: AI-generated per doc 41 (one prompt per document, callouts, grade-5 legends as `intake.example.*`); CMS SBC + MSN samples may be shown directly.
> 9. **Retention CHANGED to a plan-year rule**: retain a plan year's EOBs through the end of that plan year + the locked post-closure tail (6–12 mo), anchored on the SBC plan year; sits inside B5-6 (immediate-honor deletion still applies); documented schedule + counsel sign-off are launch-gating; the scheduler must exist before the first purge date (>1 yr post-launch) — build A3 in sequence.
>
> Sequencing confirmed: Phase 1 → Phase 2 (authored copy, generated examples, payer instructions, family rows) → Phase 3 (coverage branches) → Phase 4 (A9). Applied in `claude_code_prompt_guided_intake_decisions_phase2_2026-09-24.md`.

---

**What this is.** A second front door for Tyndale: a guided, step-by-step intake that gathers everything the audit needs, runs the analysis, shows the free results, and only then offers the paid resolution plan + chat. This does not replace the chat-first build — we're running both. Same engine, same case file, same orchestration script, same verification/reveal/unlock components. What's new is the intake route and an intake planner (§A4). Ship it behind a flag (`intake_mode: guided | chat_first`) so either can be the default per cohort.

Sections: A · the ten adjustments to the concept screens · B · screen-by-screen notes · C · what the concept doesn't cover · D · running both builds.

## A · The ten adjustments

**A1 · Colors — use Tyndale's tokens, not the concept's blues.** Teal #3E5C57 (brand, primary buttons) · Navy #1D2A38 (nav, dark banners) · Money green #2E7D5B (savings, the hero number) · Amber (deductible/OOP progress) · Citation blue #2C6E8F (source chips) · Cream #FAF7F0 (page background). Keep the concept's layout and warmth; swap the palette. The illustration style (soft landscapes) is fine in cream/teal.

**A2 · Naming — "Explanation of Benefits (EOB)".** Replace "Insurance statement" everywhere with "Explanation of Benefits (EOB)", always paired with the plain gloss the first time it appears on a screen: "the statement your insurer sends after a visit — it says 'This is not a bill' on it." Keep the concept's good line: "It may have a different name on your insurer's website." Medicare users see "Medicare Summary Notice (MSN)" instead — same slot, different label (see A4 branching). Also: the plan-rules document is officially the "Summary of Benefits and Coverage (SBC)" — that's what's printed on it, so use that name with the gloss "your plan's rulebook." Internally we say Schedule of Benefits; the user should see the words on the document they're holding.

**A3 · A real example on every ask.** Rule: any screen that asks the user for a document or a number shows a "See an example" affordance that opens an annotated example of that exact thing. The concept only does this on the SBC screen; extend to all. Build an example registry — one entry per ask, each an annotated illustration with 4–6 numbered callouts ("look for this"). Sources are already gathered and verified in `research_companions/example_documents_sources_2026-09-17.md` (the ANNOTATION SPEC section gives the callouts per document):

| Ask | Base the illustration on | Callouts |
|---|---|---|
| Itemized bill | Mayo Clinic "Understanding Your Itemized Statement of Charges" | account/visit #, per-line date, 5-digit code, description, amount, the "this is not your bill" line |
| Summary vs. itemized | same | how to tell them apart |
| Insurance card | UHC / BCBS-Michigan card anatomy, CARIN digital-card standard | member ID, group #, plan type, printed copays, Rx numbers, phone on back |
| EOB | CMS generic sample EOB + UHC / Humana reader guides | claim # + date, billed, allowed, deductible/coinsurance/copay columns, plan paid, "what you owe" |
| Medicare MSN | CMS sample MSN | "Your deductible status" box, claims table |
| SBC | CMS official Sample Completed SBC (public) | coverage period, overall deductible row, other deductibles row, OOP limit row, network vs. OON columns, coverage examples |
| Deductible / OOP "met so far" | FEP Blue Financial Dashboard + Humana SmartEOB plan page (composite) | "as of" date, deductible met/remaining, family figure, OOP met/remaining, the YTD claims list, plan-year start |

Copyright rule: the CMS/DOL SBC sample and the CMS MSN sample are federal and can be shown directly. Payer-branded guide images (UHC, Humana, Aetna) are references for drawing our own — do not embed their images. Draw clean, de-branded, non-PHI illustrations that match the real layout.

**A4 · The intake is driven by the intelligence layer — it's a planner, not a wizard.** This is the most important architectural point in the packet. The concept reads as a fixed 18-screen sequence. It must not be. The intake should be an Intake Planner that runs the engine's own "what do I still need?" logic after every capture and picks the next screen from a registry. How it works:
1. After each document lands, extract everything possible silently (locked 5a: infer first, then ask). The bill usually carries the insurer name, member ID, dates, provider; the EOB often carries deductible-met; the card carries plan identity.
2. Recompute the gap list against the five input groups (`tyndale_oop_calculation_method.md` Part 1: claim · plan rules · accumulators · patient context · encounter facts).
3. Render the next screen from the registry based on the gap list. If the card already identified the payer, skip the "which insurer" ask. If the EOB stack fully resolves the accumulators, the manual "type your deductible" screen never appears. If the SBC is on file from the Plan Library, show "confirm this matches" instead of "upload."
4. Coverage type branches the whole route. Detected from the card/bill at intake (locked 5f — seven populations): commercial · traditional Medicare · Medicare Advantage · Medicaid · duals · uninsured/self-pay · TRICARE/VA. Medicare swaps EOB→MSN, has no SBC, and uses benefit periods instead of a plan year. Medicaid typically has no deductible. Uninsured has no insurance steps at all — it routes to the Good Faith Estimate / charity-care / cash-price path. The concept is commercial-only; the planner must carry the other six.
5. Confirmations are generated, not fixed. The engine emits the list of encounter facts it couldn't resolve from paper; the UI renders that many cards. Never cap at three; never pad.
6. The readiness screen (concept #17) is the planner's own summary: what's resolved, what's unresolved, what each unresolved item limits — with an edit link on every line.

Use the existing missing-data spectrum (Tranche 1 priors + the Tier 0–3 disclosure ladder) to decide what's load-bearing enough to push for vs. what can be silently defaulted.

**A5 · Payer-specific "where do I find it" — from the insurers' own sites.** Once the card identifies the payer, every "Help me find it" renders that payer's actual menu path, not generic advice. Sources: `portal_navigation_guide_2026-07-02.md` (11 payer guides + BCBS router, locked 5h) and §5 of `example_documents_sources_2026-09-17.md` (UHC, Aetna, Cigna, Anthem, FEP Blue, BCBS Blue Access, Kaiser, Humana, Medicare.gov — with what's verified vs. not). Requirements: a payer-instructions corpus keyed by payer ID, one entry per (payer × document type × screen name); a generic fallback for unrecognized payers; instructions shown on-screen and sendable by email/text (users leave the app to go to the portal — locked 5c); and a hands-on verification pass before launch — several paths in the research are from payers' public help pages, not logged-in screens.

**A6 · Fifth-grade reading level.** Tighter than our prior 7th-grade floor. Standard: every user-facing string scores ≤ grade 5.9 on Flesch-Kincaid, enforced as a CI check on the copy registry (same drift guard that protects the script). Unavoidable terms (deductible, coinsurance, EOB, out-of-pocket) are allowed only with a gloss on first use per screen: "deductible — the amount you pay before insurance starts paying." Rewrite the concept copy accordingly; e.g., "We can't safely assume what your deductible balance was" → "We don't know what you'd already paid by then, so we won't guess."

**A7 · Getting ALL the EOBs — the timeline component.** The concept's statement timeline (#11–12) is the right idea. Spec it fully: anchor on the plan-year start read from the SBC (not assumed Jan 1) and mark the date of service of the bill being checked on the timeline · family plans: one row per covered member — family deductibles accumulate across everyone; an EOB timeline for only the patient is wrong on a family plan · three ways to fill it, offered together: upload/photo · forward EOB emails to your Tyndale address (approved build item — the biggest friction cut here) · connect your insurance (flag-gated; appears when the coverage-connection seam ships) · gap detection, as the concept shows ("missing February") — plus the honest consequence: "Without it, I'll show your share as a range." · the universal completeness confirmation (locked 5d): "I count 5 EOBs, January to June, none for anyone else on your plan. Is that all of them?" — asked every time, whether EOBs came by upload or API · track in-network and out-of-network accumulators separately; the timeline should show which each EOB fed · statements after the date of service are collected but visibly don't affect this bill's position — the concept shows this correctly.

**A8 · Progress bar.** Add a segmented progress bar under the header on every intake screen — one segment per major group (bill · card · plan rules · EOB · timeline · about you · confirmations), filling as each lands. Two rules from the intake research: frame it as already started the moment the first item lands ("1 of 7 — nice start"), and it never regresses — if a document gets reclassified, the segment stays filled and a note explains. Never a bare "Step 3 of 18" counter.

**A9 · Scanning that works very well.** Spec, in priority order: (1) live capture gating — on-device edge detection, glare/blur/skew feedback in the viewfinder, auto-capture when stable (the concept's "Snap automatically" is right); a bad photo is caught in the two seconds it's on screen, not minutes later · (2) per-page quality score with an immediate retake prompt; multi-page with a thumbnail strip; native-PDF path that skips OCR entirely · (3) document-type classification with confidence — bill / EOB / card / SBC / MSN / not-a-document — feeding the four wrong-document variants (A4 strings) · (4) itemized-vs-summary detection — the concept's scanned bill (#3) is actually a summary (category totals, no line codes); that must trigger the itemized-bill coaching (locked B5-1) with the request script, not proceed silently · (5) confidence-gated extraction — low-confidence fields become confirmation cards, never silent values; fabrication guard already covers codes · (6) PHI: on-device pre-processing where possible; server OCR only under BAA · (7) a capture test corpus — real bills/EOBs from many providers and payers, including phone photos in bad light — with extraction accuracy tracked in evals.

**A10 · What hadn't been considered — see §C.**

## B · Screen-by-screen notes on the concept

| # | Screen | Keep / change |
|---|---|---|
| 1 | Landing | Keep. "We don't assume either number is correct" is our doctrine in one line. Add the trust microcopy (Encrypted. Never sold.) near the button. |
| 2 | Bring your documents | Keep the three capture options and "I don't have the bill — start with your EOB." Add "See an example." |
| 3 | Scan | Keep auto-snap. Add live quality feedback (A9). The sample shown is a summary bill — design the itemized coaching state. |
| 4 | Reading it | Keep; real stages only. |
| 5 | Bill summary | Keep the confirmation. Add: "Did you get other bills for this same visit?" — a hospital stay produces separate bills (surgeon, anesthesia, lab) that share one deductible (§C1). |
| 6 | EOB | Rename (A2). Add example. Add "I don't have it" consequence: "I can still check the hospital's charges — but not whether your insurer's math is right, which is where the bigger errors usually are." |
| 7 | Card | Keep. Add example. "I don't have my card" → type insurer + member ID, or it's already on your bill/EOB. |
| 8 | Plan rules (SBC) | Keep — this is the one screen that already has an example. Add the Plan Library path: "We may already have your plan's rules — confirm these match?" Add skip consequence: "your share becomes a range." |
| 9 | Rules extracted | Keep. Add embedded vs. aggregate family deductible to the extracted fields; add in/out-of-network OOP max. |
| 10 | Plan year | Keep. |
| 11 | EOB timeline | Keep — best screen in the set. Extend per A7 (family rows, ~~forwarding~~ *(dropped 2026-09-21, decision 6)*, completeness confirmation). Fix the date inconsistency (bill is June 14 on #5, June 30 on #11). |
| 12 | Missing statement | Keep the honesty. Rewrite to 5th grade (A6). |
| 13 | Who was it for | Keep, but when the name on the bill ≠ the account holder, this becomes the locked attest-and-proceed step (B5-6): relationship menu + confirm line + logged + decline path; softer prompts for a teen's sensitive care and a deceased person's estate. |
| 14 | Other insurance | Keep — "we'll check it rather than assuming the second plan covers everything" is exactly the COB lock. |
| 15 | Facts only | Keep verbatim in spirit — the clinical boundary as a screen is a strong move. |
| 16 | Confirmations | Keep; count is dynamic (A4). "I don't know → unresolved" is right. |
| 17 | Readiness | Keep; it's the planner's summary. Add edit links per line. |
| 18 | Analysis | Keep; "rebuilding your deductible position" and "checking both sides" are exactly right. |

## C · What the concept doesn't cover yet

1. Multiple bills for one event. A hospital visit produces separate bills from the facility, surgeon, anesthesiologist, lab — all sharing one deductible. The concept assumes one bill. Ask, and let the audit treat them as one case. (The acceptance narrative's Maya case is four documents, one event.)
2. Everything after the analysis. The concept stops at #18. The reveal (three numbers + findings with sources), the $4.99 unlock, the plan, call mode, and chat are not designed — reuse the current build's components as they are.
3. Coverage-type branches — Medicare (MSN, no SBC, benefit periods), Medicare Advantage (EOC), Medicaid (usually no deductible), uninsured (no insurance steps — GFE/charity care/cash price), TRICARE/VA. The planner (A4) carries these; the concept shows only commercial.
4. Family plans — EOBs for every covered member, per-person rows on the timeline, embedded individual caps.
5. Summary-bill coaching — the concept's own sample bill would trigger it.
6. Attest-and-proceed for third-party bills (compliance).
7. Save and resume — people leave to find a document. Continuous autosave, magic-link return, and the honest link-expiry line ("this link works for 90 days"). The concept shows no return path.
8. ~~Email-forwarding as an intake path — approved; belongs on the EOB and timeline screens.~~ **DROPPED 2026-09-21** (Brock, decision 6): the timeline is upload-fed; forwarding is an injection surface and returns only through its own security packet.
9. "I don't have the SBC" fallback — Plan Library match, then range.
10. Trust microcopy at the moment of capture (Encrypted. Never sold. Used only for your audit.). Absent from the concept.
11. Accessibility floor — several concept screens look below 16px body. Enforce 16px / 4.5:1 / 44px.
12. Error and edge states — blurry, wrong document, name mismatch, rate limit, generic failure — all Tyndale-voiced, none dead-end. Copy exists in `33_orchestration_script.md` §5 and §10.
13. PHI retention — a year of EOBs is far more PHI than one bill; the retention schedule applies to the timeline documents too.
14. The results must attribute each finding to a side (provider / insurer / legal) — the concept's "checking both sides" promise has to land visibly on the results screen.

## D · Running both builds at once

- One engine, one case file, two intake routes. `intake_mode` flag; the guided route writes to the same case-file schema the chat-first route does, so the audit, verification cards, reveal, unlock, plan, and chat are shared code.
- The Intake Planner (A4) is the only substantial new component; the screen registry reuses the copy registry pattern (verbatim, drift-guarded, `[A]/[B]/[C]` tags apply).
- Sequence: planner + registry + capture gating first (they're the spine); example registry and payer-instruction corpus in parallel (content, mine + yours); coverage-type branches after commercial is solid.
- Measure both routes with the same evals and the same Human Review queue — the approval rate will tell us which front door produces cleaner audits.
