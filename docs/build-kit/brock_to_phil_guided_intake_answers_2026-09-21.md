# Brock → Phil: answers on the Guided Intake packet
### 2026-09-21 · Re: your nine items · Phase 1 is a go

Good catch on CO-1A — upgrading a fixed sequence into the planner is exactly the right frame, and meaningfully cheaper. Answers in your numbering. Three decisions changed from the packet; they're marked.

**Attached directly to this message** (not relying on the synced folder until the path question is settled): `example_documents_sources_2026-09-17.md` · `portal_navigation_guide_2026-07-02.md` · `tyndale_oop_calculation_method.md` · **`41_example_illustrations_spec.md`** (new — see #8) · the **18 concept screens** as images. Please confirm receipt of all five.

---

**1 · Visibility — CHANGED: guided is the only front door for now.** Not "run both." Every user goes through the simplified workflow. Take your default visibility list as the config: free-form chat and the quick-actions grid **hidden**; cases, settings, the Record, and post-unlock chat **kept**. Cohort split is 100% guided. The chat-first intake stays in the codebase behind the flag — not deleted, not shown. Keep recording `intake_mode` on every case so Human Review still sees the route.

**2 · Fifth-grade rule — ratchet.** New `intake.*` keys strict at ≤ 5.9 in CI from day one. The existing 136 keys are grandfathered until touched; report their scores, don't fail them. I'll rewrite as I author.

**3 · Scanning — A9 supersedes N1 and B2, explicitly.** N1 rejected a *fake* locking-on overlay; B2 rejected an *unverifiable* badge. Both were right. A9 asks for the **real capability**: live edge detection plus glare/blur feedback in the viewfinder, tied to actual capture quality. **Priority: after the planner and the timeline are working — Phase 4 as you proposed, costed as its own phase.** A bad photo is the most common way an audit goes wrong, so it's worth the project; it just isn't worth doing before the thing it feeds. Native capture stays parked on DL-44.

**4 · Paywall — pass through with the honest beta line.** Render the unlock moment, state "free while we're in beta," and proceed. **This is temporary and tracked: the moment the flow is stable end-to-end and billing lands, the paywall goes live.** Please carry it as an explicit launch-checklist item so it doesn't drift.

**5 · Files and screens — attached above.** Same folder gap in the other direction; let's close it properly: **reply with the absolute path of the directory you sync from**, and I'll compare it against mine. Until then, anything referenced gets attached.

**6 · Email forwarding — CHANGED: dropped for now.** You're right that it's an injection surface needing its own security design, and we're not going to carry that before launch. Remove it from the timeline options entirely; the timeline is upload-fed. If we revisit, it starts with your security packet, not a product spec.

**7 · Link expiry — use the real 15 minutes.** "90 days" was placeholder copy on my side; strike it. State the true expiry in the resume copy and make sure the resume path re-issues a fresh link cleanly.

**8 · Illustrations — AI-generated.** `41_example_illustrations_spec.md` gives you one ready-to-paste image prompt per document (itemized bill, summary-vs-itemized, card, EOB, MSN, SBC, portal deductible screen, and the EOB timeline helper), the numbered callouts to overlay, and the legend copy already written to the 5th-grade floor as `intake.example.*` keys. De-branded, non-PHI, our palette. The two federal samples (CMS SBC, CMS MSN) can also be shown directly. The 18 concept screens are attached for visual context.

**9 · Retention — CHANGED to a plan-year rule.** The EOBs are needed to maintain the case file for as long as they're load-bearing, and they're load-bearing for the plan year they belong to (deductibles and out-of-pocket reset at the plan-year boundary, and plans change). So: **retain a plan year's EOBs through the end of that plan year plus the locked post-closure tail (6–12 months, long enough to close any case that straddles the boundary), then purge.** Two notes: anchor on the **plan year from the SBC, not the calendar year** — many plans don't start January 1; and this sits inside the locked B5-6 schedule, it doesn't replace it (the immediate-honor rule for a verified patient deletion request still applies).

On the gate: the **documented schedule and counsel's sign-off are launch-gating**; the scheduler itself must exist before the first purge date, which is more than a year after launch. Build A3 in sequence, not as a blocker to Phase 1.

---

**Sequencing confirmed:** Phase 1 (planner, registry, flag, timeline upload-fed, attest, save/resume at 15 min, results on the existing reveal) → Phase 2 (my content: authored `intake.*` copy, the generated examples, payer instructions; family rows) → Phase 3 (coverage-population branches) → Phase 4 (A9 scanning). Non-commercial users in Phase 1 get the one honest line and the chat-first hand-off — right call.

**From me next:** authored `intake.*` copy at the 5th-grade floor; the payer-instructions corpus entries keyed by payer ID from the attached guide; verification of the three ⚠️ portal paths before you build against them.

— Brock
