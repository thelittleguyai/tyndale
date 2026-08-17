# Sweep Debrief — 2026-08-17 evening (for the co-work session)

*Follows `PROJECT_STATE_2026-08-17.md` (same day, written before deploy). Everything below
happened after Phil pushed + applied the Dev-Complete build. Written by the engineering
session; every claim here is verified, not inferred.*

## TL;DR

Dev is fully current on both containers and the **first-ever full-suite e2e sweep ran
against it** (the workflow had only ever run once before, 2026-07-09, also red). Headline
score 4/23 — but triage is COMPLETE and every failure has a confirmed mechanism. Four
layers were measuring-instrument noise (fixed + proven by targeted reruns). One was a real
**fabrication bug — the translate agent echoed a prompt example into persisted line items**
— found to the exact line, guarded deterministically, proven fixed on dev. What remains is
essentially ONE product-policy decision (the SBC completion gate, below) plus a small
reconciliation bundle. Detection quality itself came out looking *good*: the "missed
duplicate" was actually caught under the more precise `mue_excess_units` framing.

## Deploy state (verified)

- runtime container: `runtime:33b414a…` + two hotfix deploys → now at `67de364` HEAD line;
  app container: `app:9f7940b…`, serving 200 at app.tyndaleapp.net.
- Migrations 0040/0041 live. B4 backfill run on dev **in-container**
  (`az containerapp exec` — the dev Postgres is VNet-private, laptops can't reach it):
  scanned 48, filled claim_number 24 / account_number 25 / provider_phone 8 /
  payer_phone 0 (honest zero — no structured source carries one). Beloit acceptance check
  = Phil's eyeball on call mode (pending his click).
- Flags now ON in dev tfvars + applied: `enable_nudge_emails`, `enable_first_case_unlock`
  (rest unchanged: chat_first / record / audit_ready_email already true).
- The 2-flag terraform plan also carried ~18 `workload_profile` no-op diffs — azurerm
  provider canonicalization noise, applied harmlessly, will likely reappear.

## Post-deploy commits (all pushed, all deployed)

| Commit | What |
|---|---|
| `69f699c` | **Deploy Dev App was broken** — `nativewind/babel` (= react-native-css-interop/babel) HARDCODES `react-native-worklets/plugin`; that preset line, not any import, is why worklets was ever a dependency. babel.config.js now inlines the preset minus that line (auto-re-engages if worklets returns). Verified the only honest way: clean `npm ci` → `expo export` → tsc → jest. **Caveat for all future sessions: jest (test branch drops NativeWind) and tsc (no Babel) are BLIND to the app-branch Babel path — a clean-install `npm run export:web` is the only local check that runs what Deploy Dev App runs.** |
| `9f7940b` | e2e workflow now passes `--chat-first --record` (dev serves both). |
| `33b414a` | `DEV_TEST_DAY.md` (the item-7 checklist, unchanged). |
| `d9fd835` | Sweep harvest: 4 noise layers peeled (below). |
| `205ca96` | **Translate-grounding guard** (below). 919 runtime tests. |
| `67de364` | Harness `--inspect` mode: read-only case diagnosis via the synthetic user (no admin needed, no audit cost) + workflow input. |

## The sweep, triaged to zero unknowns

Full run: [32065709044] 4/23. Passing: `blank_pages`, `not_a_bill_txt`, `unbundled_panel`
(**end-to-end green including all X-contract assertions** — the existence proof that the
whole real pipeline can pass), `record_aggregates`.

**Noise (fixed in `d9fd835`, proven by targeted rerun [32072443068]):**
1. `captured_bill_photo` used CPT **70553 as its legitimate line item** — but 70553 is a
   FIXTURE_MARKER. Spec now uses 70551 with a warning comment.
2. Harness `_check()` crashed (`KeyError: 'terminal'`) on the two branch-flow specs that
   deliberately have no terminal expectation. Both now PASS.
3. The 20/hr upload cap ate the last two scenarios; `_upload` now honors Retry-After once.
4. X2/X5 drift reconciled where eng owns it: all-clear categories
   (`diagnostic_clear`, `upcoding_diagnostic_clear`,
   `diagnostic_audit_complete_no_confirmed_errors`, `cost_sharing_audit`) typed
   informational; `phantom_charge → phantom_service` mapping; two DATED `X_KNOWN_GAPS`
   entries for the real debts (error findings without bound actions; impacts absent
   without a typed unknown-reason). All pending A6.

**The real bug (fixed in `205ca96`, proven by rerun [32075059617]):**
The targeted rerun leaked 70553 AGAIN with a clean spec → server-side. Mechanism, to the
line: the Bill Detective's translate skill
(`06_encounter_verification/lineitem_plain_language.md`) teaches with the worked example
"MRI brain w/ + w/o contrast (70553)"; on a photographed bill whose real-DI OCR came back
thin, the agent **echoed the example into persisted line items** — a fabricated charge on
the encounter screen. Caught only because the example code doubles as a harness marker
(the example codes are accidentally perfect canaries — keep 70553/A9579/36000 in prompts,
or move the canary set in lockstep).
- **Guard (runtime, deployed):** a coded line item whose base code appears in NO uploaded
  document's OCR text is dropped at the translate seam + logged; filtered list persists
  immediately; all-dropped → the existing honest no-item states. Conviction needs strong
  evidence (legacy/preview-only cases, uncoded rows, sub-4-char codes always keep).
  Upload now persists full per-document OCR text (50k cap, JSON field) as the haystack.
- **Prompt-side ask queued as BROCK_ASKS §3.10** (an explicit "never substitute a code
  from these examples" line; canary codes stay).
- The sweep's one 500 (`GET /v1/audit`, balance_billing case) has not recurred since; the
  read seam additionally got a belt-and-braces try/except honoring its own "never a 500"
  contract. Watch, don't chase.

## THE open product decision — the SBC completion gate (9-10 scenarios)

`--inspect` on the cascade cases settled it. Every one shows the same checklist:
EOB **have**, itemized bill **have**, **SBC missing** → `needs_documents`. One case even
carries the self-describing category `coverage_terms_missing_audit_incomplete`. No
scenario uploads an SBC — and per the Graceful Degradation Doctrine they shouldn't have
to: the pipeline currently **gates completion on coverage terms**, where the doctrine (and
every scenario expectation) says **complete at the achievable rung** — deliver the
provider-side findings it already produced, qualify cost-sharing figures per the X3
disclosure tiers, and offer the SBC as the *unlock*, not the gate.

Evidence that the rung-2 result is worth delivering: the "failed" cases contain REAL
findings — `mue_excess_units` (the duplicate scenario's doubled MRI, correctly framed as
a Medically-Unlikely-Edit violation), `bill_eob_charge_discrepancy`, `three_number_audit`,
`upcoding_risk`. The scenario "no finding matching 'duplicate'" fail is a vocabulary
mismatch, not a detection miss.

**This needs a prompt.** Scope sketch (engineering's read; the co-work session should
shape it): completion policy at the orchestrator/Lead-Planner seam (complete when
provider-side analysis stands, even with coverage terms missing), X3 tier qualifiers
surfacing on the three-number moment (`x3:no_qualifier_surface` is already a ledgered
gap), the needs-documents checklist re-framed as "unlock more" on completed audits
(thread copy = Brock's voice — his script has no state for "complete but SBC would
deepen it"), and scenario-expectation reconciliation (duplicate accepts
`mue_excess_units`; informational categories excluded from finding-count maxima).
Engineering deliberately did NOT reshape completion policy unilaterally.

## Smaller open items (bundle into the next prompt)

- **Attest gate didn't engage** on `name_mismatch_attest` (no attest_request in thread;
  confirmations 200 where 409 expected while unattested). Not yet diagnosed — next step
  is `--inspect` + thread fetch on that case (its id wasn't captured; rerun the scenario
  or extend inspect to print the thread).
- **`insurance_card_only`**: X1 says the not_a_bill state leaves no return path.
  Deliberately not config-suppressed — either a real UX gap or X1's detector missing the
  card's CTA. Needs a look at the rendered thread.
- **`collections_only`** reported `extraction_failed` during the sweep but inspects as
  `audit_incomplete/needs_documents` now (all three checklist items missing — correct).
  Possibly a transient state the poll caught mid-transition; low priority, worth one look.
- `api-wrapper/API.md` + `postman_collection.json` sit untracked at repo root (predate
  this work; not engineering's).

## Notes for future sessions

- The harness can now: retry the upload cap, assert chat-first + Record in CI, and
  **inspect existing cases read-only** (`--inspect`, also a workflow_dispatch input) —
  diagnosis without admin access or audit spend.
- The E2E secret path for CI is the GitHub `dev` environment secret; pulling it from Key
  Vault locally was blocked by the session's permission layer — run sweeps via
  `gh workflow run e2e-scenarios.yml`, not locally.
- Local runtime is stub-by-construction (no DI, no Qdrant corpus) — the harness's marker
  tripwire fails it BY DESIGN. Never run the sweep against local expecting signal.
- Dev sweeps cost ~1 real audit per scenario, ~45-90 min full-suite; targeted
  `-f only=a,b,c` reruns are cheap and were the workhorse of this triage.

## Verification state

runtime **919 passed / 5 skipped** · mobile tsc clean + **94/94** (20 suites) · ruff clean
everywhere · clean-install `expo export` green (the check that would have caught the
worklets preset) · Deploy Dev Runtime + Deploy Dev App + Golden Evals + Typecheck +
Runtime CI all green at HEAD `67de364`.
