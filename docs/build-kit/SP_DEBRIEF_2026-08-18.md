# SP Debrief — 2026-08-18 (for the co-work session)

*Follows `SWEEP_DEBRIEF_2026-08-17.md`. Covers the full execution of the "SBC Completion
Policy + Sweep Remainders + Wrapper Test Suite" prompt AND the post-STOP work the day
produced (SendGrid diagnosis, the attest-500). Every claim verified; sweep numbers are
from real dev runs.*

## TL;DR

All four workstreams shipped and are deployed to dev. The full sweep moved **4/23 → 17/23**
on the rung-2 build, and two post-STOP fixes proven by a targeted rerun bring the honest
standing to **19/23**. The four remaining rows are named, owned, and none is an unknown:
one deliberately-held eng design (finding-level grounding), two Brock items (A6 taxonomy,
§3.10), two product calls (collections terminal, NSA flag). The SendGrid mystery resolved
to an account-protection event, not a config problem — guarded in code, one Phil check
outstanding. HEAD `0f3a9d5`; runtime 936 tests, mobile 99, wrapper 33+1todo.

## Workstream 1 — the SBC gate fell (28ee873)

Phil's ruling implemented engine-side, deterministic, document-grounded:

* `app/sources/cost_share_model.py`: standard deductible-then-coinsurance arithmetic swept
  over the Sprint-C priors (`compute_range`'s intended use). Bounded [0, anchor]; range
  collapses toward stated coverage values.
* `_rung2_three_numbers` (orchestrator): anchors ONLY on document-stated money — EOB
  allowed > EOB billed > itemized total, read from stored per-document OCR text via the new
  public `eob_money_figures`. **Anchors no document stated stay None** (schema: optional
  `provider_billed` / `eob_member_responsibility`; new `tyndale_computed_low/high`,
  `computed_source: "agent"|"engine_rung2"`). No anchor at all → the true needs_documents
  shape survives (Beloit day-one). Engages at audit time + on reads of COMPLETED cases;
  never flips a persisted incomplete terminal on a GET.
* **X3 closes its ledgered gap** (`x3:no_qualifier_surface` DELETED — enforcement on): the
  moment card renders the qualifier in the figure's own visual unit; tier ≥2 renders the
  RANGE AS THE FIGURE ("between $X and $Y until I see your deductible"), tier 1 point form,
  tier 0 forbidden. Mobile renders qualifier + range + honest "Not on file yet" anchors.
* **unlock_more state**: a COMPLETED audit with unchecked inputs re-frames the have/need
  checklist as deepening, not finishing. `unlock_more.intro` / `unlock_more.item_hint` are
  DELIBERATE `[PLACEHOLDER-eng]` seeds — **the staging boot blocks on exactly these two
  keys** (asks §3.11), and the placeholder-gate tests pin that exact state in both
  directions (a stray placeholder fails; simulated-authored copy proves staging boots the
  moment Brock lands the words).
* Scenario reconciliation: ten cascade scenarios assert completion **with a qualifier**
  (`_qualifier_checks` over the thread); `duplicate` accepts `mue_excess_units` via `|`
  alternatives; informational categories no longer count against `max_findings`.

## Workstream 2 — sweep remainders (4f5eed8, 66b0a1e, 4c8e71b)

* **Attest root cause**: the synthetic e2e user was minted NAMELESS, and the matcher's
  correct conservative rule ("missing data never fabricates a mismatch") silenced the gate
  for every harness run. The identity now carries the generator's suite name
  (Jordan Testpatient), the persisted dev row backfills on next mint, regression pins the
  full geometry.
* **X1 detector taught the product's real affordances**: typed `next_action` IS a return
  path (the N2 branch card button); `not_a_bill` is an OPEN status (a redirect, not a
  closure — uploads still attach); `unlock_more` checklists count like needs-docs
  checklists. Also fixed a latent test-isolation bug the pinning exposed.
* **Poll-to-stable**: the harness accepts a terminal only after two identical reads —
  collections' "transient" was a transition frame.

## Workstream 3 — wrapper suite (46886e6)

34 node:test tests, zero new deps, wrapper behavior untouched (verbatim `serverCore.ts`
split for ephemeral-port testing). Coverage: full server contract (auth/gates/error
mapping incl. leak-free 500), fixture-driven normalization (committed sandbox bundles;
absence-never-invented), envelope guards, token-store semantics with RESTART-LOSES-
EVERYTHING in the test name, and a two-way docs-drift gate (routes ⇄ postman ⇄ API.md —
both files now committed). **The pre-flip PHI item is a visible node:test `todo`**:
`OneUpApiError` embeds the upstream body in `error.message`. New `wrapper-ci.yml` on PRs.

## Workstream 4 — small (5b129ed)

Canary-code lockstep note lives at `intelligence-layer/prompts/README.md`; DEV_TEST_DAY
§0.3b pins warm replicas (compute.tf hardcodes `min_replicas`, lines ~108/~1089 — corrected
in 3b3206c).

## Post-STOP chapter (same day)

* **SendGrid 401s — resolved to account protection, not config** (93ad148, fecc91e):
  chased end-to-end — key valid with full scopes, KV == tfvars (plan: no changes), the
  CONTAINER holds the identical key (hash-verified in-exec) and SendGrid answers 200 from
  the container's own egress. The failures were mail-send-only, during the sweep window,
  when ~15 sends hit `@e2e.tyndale.test` (a reserved, undeliverable TLD) in 45 minutes — a
  spam-trap signature that trips provider pauses. **Guard shipped**: synthetic-suffix
  recipients short-circuit before any network call; exactly-once ledgers stay unstamped.
  Outstanding: Phil's magic-link-to-real-address check (account healthy vs still paused).
* **The attest-thread 500** (0f3a9d5): `MessageKind` never contained `attest_request` —
  the bridge wrote it since CS1, and the FIRST thread to contain one (possible only after
  the identity fix) 500'd `GET /v1/conversations/{id}` on ValidationError. Python Literal +
  TS mirror extended. **Structural armor**: `test_thread_kinds` source-scans the bridge for
  every kind it writes and fails on any not in the Literal — the whole 500 class is closed,
  not just this instance. This would have greeted the first real name-mismatch user
  (Phil's Beloit case is exactly that shape).
* **Decline checks had never run**: they posted to `/v1/messages`, a route that has never
  existed on dev. Now post to the real `POST /v1/conversations/{id}/messages`.
* **Proof rerun: 2/2** — `name_mismatch_attest` reaches `attest_gated` with a serializable
  thread + 409s; `chat_declines` passes including the no-prediction-language assertion.

## The remaining four sweep rows (all named, none unknown)

| Row | Cause | Owner / next |
|---|---|---|
| `captured_bill_photo` | prompt-example bleed into AUDIT PROSE (findings/summary) — one layer past the translate guard | **the one held eng item** — needs a prompt: what does the product do with a real finding whose prose cites a hallucinated code? (drop / strip / flag+degrade). Brock's §3.10 line is the prompt-side half. |
| `clean_bill_matching_eob` | agents mint unbounded all-clear category phrasings (`diagnostic_audit_clean`, `coverage_math_audit`, new each run) | Brock A6: the taxonomy; interim = upstream `presentation: informational_context` typing (the ledgered X2 debt) |
| `collections_only` | STABLE `extraction_failed` (designed terminal for recognized-doc-no-line-items) vs scenario's `audit_incomplete` | product-semantics call (Phil/Brock): change the state machine or the expectation |
| `balance_billing_mismatch` | completes, but no balance finding — likely behind `enable_nsa_checks=false` on dev | confirm the gating (eng, quick), then Phil's flag call |

## Also open (infra / people)

* Qdrant `payer_policies` collection missing on dev (init + ingest — Jonas or eng).
* SendGrid magic-link verdict (Phil, 1 min) → then close/reopen gather-list item 1.
* Brock package: §3.9, §3.10, **§3.11 (staging-blocking)**, A6, priors table (now
  USER-VISIBLE via rung-2 ranges — promoted).
* Test-day preconditions (`DEV_TEST_DAY.md` §0): warm replicas, sweep, walkthrough.

## Notes for the next prompts

* The harness now: polls-to-stable, retries the upload cap (Retry-After), asserts
  qualifiers, consults the X2/X5 known-gaps ledger visibly, and has read-only `--inspect`
  (also a workflow_dispatch input) for case diagnosis without admin access or audit spend.
* The rung-2 range's honesty depends on Brock's priors — placeholder values render today.
* `test_thread_kinds` and the placeholder-gate tests are the two new structural gates a
  prompt can rely on (bridge kinds ⊆ MessageKind; placeholders == exactly the §3.11 set).
* Verification state at HEAD `0f3a9d5`: runtime **936 passed/5 skipped** · mobile tsc
  clean + **99/99** · wrapper **33 pass + 1 todo** · all deploys green · dev fully current.
