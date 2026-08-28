# Phil → Brock — re: 38 · Content Program + Tranche 1 (2026-08-22)

Tranche 1 received — this is exactly the drop the system was built to take. Answers to your §4, in order:

**1. Schema extension: confirmed as proposed.** `rule_class` enum, `applicable_codes` optional (required only for `provider_coding`), `responsible_party`, and the seven payer-side `rule_type` values — implemented exactly as you wrote them, extend-not-replace. One coherence note rather than a change: your payer-side `rule_type`s and the 14-value `error_type` enum in the 37 draft are two levels of the same taxonomy (rule_type = what the rule checks, error_type = how a finding is classed), so we're adding a mapping note to the 37 draft showing which feeds which — glance at it when you review that file, but don't wait on it. Engineering will send you the exact authoring shape + one example payer-side entry when the schema lands (days, not weeks), so author Tranche 2 against that. `responsible_party` will drive finding attribution in the UI as the master UX spec requires.

**2. Ingestion path: data file — and the seam already exists.** `missing_data_priors.py` was built with a tranche loader: it reads JSON files from a drop directory, and each entry's arrival is the activation switch (your per-entry values flip `placeholder: false`, which un-suppresses the user-visible range for that entry only). So: keep authoring tables exactly like §2 and we convert to tranche JSON on our side — or if you'd rather author JSON directly, we'll send the shape. Either way no code change per tranche, which was the design goal.

Implementation notes on Tranche 1, all per your rules:
- The two DO-NOT-ACTIVATE entries (lab multiple, regional substitution) are being tombstoned in code with your language, plus a test asserting they can never render a number.
- Rate substitutions (§2.1) land as a separate Tier-3-only benchmark table — the render path will refuse point-form for them structurally.
- `medicare_participation`: building the specialty-aware CMS opt-out NPI resolver seam now; the NPI file ingestion follows. Until it lands, unresolvable → silent participating-with-low-confidence internal flag, nothing user-facing.
- Regime-switchers (§2.4): confirmed none are in the priors sweep; adding a regression test that a missing switcher always goes to the verification ladder, never a defaulted range.
- Open-ended highs ("$2,000+"): stored at the stated number with the open-endedness recorded in the entry note — flagging so you know the rendered range says "or more" rather than inventing a cap. Shout if you want different handling.
- Agreed on sweep timing: before/after runs after Tranche 2, since Tranche 1 changes honesty, not detection.

**3. The three draft files: already delivered — they've been in the shared `Tyndale Final/` folder since 8/19** (copied there after the attachment channel failed twice). If you don't see them, say so and we'll find another channel — but A1–A7 should be unblocked on your side right now.

Sequencing ack: your tranche order works on our end. Tranche 2 is the one we're staged for — the schema will be waiting for it.
