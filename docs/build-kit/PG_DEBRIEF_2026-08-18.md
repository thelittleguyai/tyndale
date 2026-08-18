# PG Debrief — 2026-08-18 evening (for the co-work session)

*Follows `SP_DEBRIEF_2026-08-18.md`. Covers the full execution of "Prose Grounding, Priors
Gate, Collections Semantics, Last Sweep Rows" under Phil's three rulings, plus the same
evening's discoveries. All sweep numbers are real dev runs; HEAD `54b6861`.*

## TL;DR

**The prompt's target is met: every sweep row is green or Brock-owned-and-ledgered.** Full
sweep 19/23 with all four failures self-diagnosed; the fix round flipped all four in a
targeted proof (4/4). Two rows are deliberately "ledgered-green" — they PASS while
printing a dated gap note on every run (balance-billing awaits the NSA seed; clean-bill
names the A6 vocabulary dependency). The prose-grounding guard is live and proven both
ways: it killed the photographed-bill fabrication AND its one false-positive class
(unbundling reference codes) was caught by the sweep and fixed structurally. Separately:
dev Qdrant turned out to be missing THREE of four collections — every past dev audit ran
without rules/laws/payer retrieval — schemas now exist, corpora await ingestion. Runtime
**955 tests** · mobile 99 · wrapper 33+1todo.

## Ruling 1 — prose grounding (drop-if-basis, scrub-if-incidental)

* New pass after the agents, before any terminal: `app/sources/prose_grounding.py` +
  `_ground_prose` in the orchestrator. BASIS (a code the finding structurally depends on,
  absent from every document's stored OCR text) → the finding is DELETED, counted as
  `grounding_drop:{category}` in DOCTRINE_VIOLATIONS (ops panel). INCIDENTAL
  (parenthesized prose reference on a really-grounded finding) → span-stripped; inline
  mentions are never Franken-prosed — they drop. LP summary: one `compose_final`
  regeneration with the §3.10-style correction inline (consumes the regen budget), then
  degrades to no-summary. Conviction rules carried whole from the translate guard.
* **The false-positive class, found by the sweep itself**: an unbundling finding cites
  the correct PANEL code that is deliberately absent from the bill. Fix:
  `structured_code_claims` splits PRESENCE claims (facts-tree code keys) from REFERENCE
  codes (`correct_*`/`should_*`/`bundl*`… keys + everything in recommendation/legal_claim).
  References never convict, vouch their own prose mentions, and kept findings' references
  vouch the summary. Residual accepted in comments: laundering a fabricated code through
  a reference key is a lesser harm than dropping every legitimate unbundling finding.
* Acceptance: `captured_bill_photo` PASS and `unbundled_panel` PASS on dev.
* HCPCS shape bug found while testing: `[A-Z]?\d{5}` misses letter+4-digit codes; the
  shape is `(?:[A-Z]\d{4}|\d{4,5})` everywhere now.

## Ruling 2 — priors gate

`InputPrior.placeholder` (default True — a new unreviewed entry is placeholder until
flagged). `rung2_range` tracks whether any CONSUMED prior is placeholder (stated coverage
never counts); the emit seam suppresses low/high while true → the figure ships point-form
with the point qualifier. **Brock's researched table is the activation switch** — per-entry
`placeholder=False` turns ranges on with zero code change. Tests both ways; the harness
qualifier check accepts both forms, so the sweep is stable across the transition.

## Ruling 3 — collections semantics

Recognized doc + readable dollar + no line items → `audit_incomplete/needs_documents`
with the chase checklist (the Beloit day-one behavior); `extraction_failed` reserved for
the genuinely unreadable. `ExtractResult`/TS gain `needs_documents`; the encounter screen
renders the third honest variant ("One more document finishes this"). The harness resolves
the case terminal instead of POSTing confirmations at an extract-terminal state (the 400s
in the first PG sweep). `collections_only` AND `summary_bill_only` PASS.

## The last rows

* **balance_billing**: gating confirmed — `enable_nsa_checks=false` suppresses NSA
  assertions via the regime-provenance assumption (doctrine-level, not a hidden code
  path). Flag stays OFF per Phil. Scenario asserts gated behavior; ledger entry
  `scenario:balance_billing_nsa_seed` prints on every run. PASS + visible.
* **clean_bill**: read-seam stamps `presentation=informational_context` by category
  FAMILY (stems `_clear/_clean/_audit/no_confirmed/_complete/_pass`) — but ONLY for
  findings claiming no money (a moneyed stem-match is the logged escape hatch). Coherence
  test pins that no mapped error category can ever stem-match. The vocabulary is provably
  unbounded (new mint each sweep: `diagnostic_audit_clean`, then `diagnostic_pass_complete`)
  — `scenario:clean_bill_a6_vocabulary` prints on every run so a future stem miss reads
  as the known A6 dependency. PASS + visible.

## The Qdrant discovery (reframes past detection-quality data)

Phil's in-container init revealed dev had only `billing_codes` — `error_detection_rules`,
`laws_regulations`, `payer_policies` did not exist. **Every dev audit to date ran with
rules/laws/payer retrieval ERRORING** (not even empty results). This is consistent with
everything the sweeps showed: strong arithmetic/MUE findings, weak legal_claims and
citations (the ledgered `no_line_item_ref` family). Schemas now exist (tools degrade
honestly to empty); the corpora await Brock's content + Jonas's ingestion. **When the
corpora land, run a fresh sweep specifically to measure the detection-quality delta.**
Jonas notes: qdrant-client 1.18.0 vs server 1.12.4 (outside supported skew — pin or
upgrade); collection creation outlived the default client timeout (possible resource
starvation on the dev Qdrant container).

## Also closed this evening

* **SendGrid**: resolved as an account-protection pause (spam-trap signature — ~15 sweep
  emails to the undeliverable `.test` domain), NOT a key/config problem (key valid,
  KV==tfvars, container key hash-verified, egress accepts). Guard shipped: synthetic
  suffixes (now `settings.synthetic_email_suffixes`, env-extendable) short-circuit before
  any network call. Outstanding: Phil's magic-link check to confirm the account is
  unpaused.
* Grounding-drop counts: exact numbers live in DOCTRINE_VIOLATIONS on the admin ops panel
  (`grounding_drop:*` / `grounding_scrub:*` / `grounding_summary_*`) — a log-tail can't
  enumerate a 70-minute sweep.

## Open board by owner

* **Brock (the whole critical path now)**: §3.11 (unlock_more copy — the ONLY staging-boot
  blocker), A6 taxonomy (ends the stem interim), §3.10 grounding line (the prompt-side
  half of the guard), the priors table (= range activation switch), §3.9, the NSA seed
  (activates balance-billing), and the rules/laws corpora content.
* **Jonas**: corpus ingestion runs; qdrant version skew + container sizing; (parked) the
  wrapper pre-flip items.
* **Phil**: SendGrid magic-link check; test day per DEV_TEST_DAY.md.
* **Engineering**: nothing held — the board is clean pending the above.

## Notes for the next prompts

* New invariants to rely on: bridge kinds ⊆ MessageKind (source-scan test); placeholders
  == exactly the §3.11 set; no mapped error category stem-matches informational;
  scenario-level gates print their ledger entry every run.
* Accepted residuals, documented in code: reference-key laundering (prose grounding);
  stem lag on novel all-clear mints (A6 closes); rung-2 point values derive from
  placeholder priors until Brock's table (the ranges are suppressed, the base shows).
* The sweep is now self-explaining end to end: ledger notes, known-gap notes, Retry-After
  waits, and poll-to-stable all print inline in the run log.
