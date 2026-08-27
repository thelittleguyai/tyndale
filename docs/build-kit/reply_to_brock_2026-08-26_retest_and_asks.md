# Phil → Brock — everything you flagged is live on dev; re-test list + what's waiting on you (2026-08-26)

All of your 08-22 feedback is deployed to dev as of today — one pass on your phone covers it all. Here's the tour, then the queue that's yours.

## 1 · Re-test list (everything, live now)

- **Camera capture**: "Use this photo" + "Retake" are a proper side-by-side row below the preview (the hover bug was the preview overflowing its slot — fixed at the root). Multi-page: "Done" + "Take another picture" side by side; page count lives in the header.
- **The loading screen**: while the audit runs you now see ONLY the "Working on your audit" card — no chat bubbles, no questions overlapping spinners. Analysis and questions appear when the run completes or properly pauses (a pause shows a calm static card, no spinners).
- **Your UMC case, both bugs**: "what's your relationship to Payments (since last statements)?" is structurally impossible now — extracted strings pass a plausibility gate before entering any copy, and junk degrades to the generic form. And a summary-page statement like yours (page 1 of 4) now gets in-thread coaching that an itemized bill is needed — re-upload the same photo and you'll see both behaviors. (One honest caveat: the gate is conservative — a provider literally named "Total Care Clinic" would also degrade to generic. Acceptable trade, flagging it.)
- **The checklist is now the completion hub you asked for**: per-item Add buttons (upload opens pre-tagged to that document), the four coverage-number fields + visit confirmation with tap-chips, "What is this?" explainers on every item, and the composer always available — type "my deductible is $2,000" and it pre-selects the field; Save/tap remains the only state change. The part worth watching: enter a deductible-met figure and the audit's range visibly tightens on the next update — your Tranche 1 tier contract driving the UX, exactly as designed.
- **The homescreen**: header with "+ Check a bill," honest welcome banner, recovered-to-date (now strictly confirmed-outcome money — the old card was showing a proxy figure, which we treated as a bug per your own substantiation rule), open-cases stat, case cards with real status pills including dated deadlines, your quick check-in card with the three outcome chips, floating chat button.

## 2 · 16 script keys PROPOSED, wanting your authoring pass

All seeded live with interim copy in `33_orchestration_script_v2_DRAFT.md`: the 8 checklist explainers (what/where/example pattern), the checklist acknowledgment line, 4 home-banner keys, and your 3 check-in chips. Two doctrine notes sit beside them in the draft — please author within them:
- **Banner honesty constraint**: the welcome line may only state true things about case status until proactive monitoring (B8) exists — "deadlines watched / numbers re-checked" is test-banned until then.
- **Check-in chips are routes, not outcomes**: tapping "They're fixing it" routes the follow-up; it never marks the case resolved — resolution stays with the confirmation flow.

Still open from before: the capture-screen labels, `{itemized_request_script}` (your UMC case now triggers the coaching path that wants this script — it's live with interim copy), the freeform opener pair, and the A4 wrongdoc strings.

## 3 · Mockup elements held back, one line each

- "Deadlines watched, numbers re-checked" banner → B8 isn't built; phrases are test-banned until it is.
- Estimate Costs / Find a Doctor / Plan a Visit tiles → §5 features not started; they were live dead buttons and are removed.
- Connect your plan tile → appears automatically when the coverage-connection seam ships (flag-driven).
- "Waiting on insurer" pill → no such tracked state exists; the honest equivalent (dated-deadline pill) shipped.
- Blue Shield PPO card header → plan identity isn't reliably extracted yet.
- Deductible/OOP progress bars → shipped, but ONLY from real values ("from your entries" / "from your SBC") — a prior can never become a bar.

## 4 · One decision you owe us: the fabrication canary

The e2e sweep's fabrication tripwire (planted marker codes that must never appear in output) tripped on a TRUE POSITIVE of the wrong kind: the Bill Detective, reasoning correctly about a 70551 MRI bill, wrote in its internal analyst notes "lowest complexity of the 70551/70552/70553 family — no upcoding signal." 70553 is one of our canary codes; naming it there is legitimate code-family reasoning, not fabrication — nothing user-facing carried it. Two options:

- **(a) Scope the scan** to user-data-bearing fields (persisted line items, amounts, user-facing prose) and stop scanning internal analyst notes — cleaner, but permanently blinds the tripwire in the field where reasoning happens.
- **(b) Ledger this exact signature** (this field + code-family-reasoning context) and keep scanning everything — the narrowest possible weakening; any new hit still fails loudly with tooling that names the exact location.

Engineering leans (b) — this tripwire has caught real fabrication once and we'd rather ledger one known-benign signature than retire a whole field from surveillance. Your call as detection owner; a one-word reply ("ledger" or "scope") unblocks the sweep going back to fully green.

## 5 · Standing queue (unchanged, restated so nothing silently ages)

A1–A7 file review (files in `Tyndale Final/` since 08-19) · Tranche 2 payer-side rules against the confirmed schema — the golden payer rule is seeded and retrieval-tested, so your rules land into a proven path; note 3 of your proposed rule_types await your error_type mapping glance in the 37 draft · the judge rubric · ~~§3.11 unlock_more copy~~ *(struck 2026-08-27: your v1.1 authored both keys verbatim on 08-18 — this ask was already closed when this reply was written)* · the $504,100 substantiation or removal · opener/capture/itemized/A4 copy per §2 above.

The build is in the best shape it's been — today's re-test is the fun kind.
