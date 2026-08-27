# Tyndale — Project State (2026-08-17)

> **Scoreboard re-counted 2026-08-27** (audit group 6): §1's figures and §6.3's checker
> status are current as of `ce1531b`. The NARRATIVE sections still describe the 08-17
> snapshot — ten days of work (capture/progress/identity fixes, the checklist completion
> hub, the homescreen, three audit sweeps) landed since; see `git log e34bfbf..` and the
> two reply_to_brock docs for what moved.

**What this is:** the current-state deep dive for the next Cowork planning session, written
against the tree at `e34bfbf` and verified against the deployed dev environment — not
recalled from prior session notes. Where a number appears, it was counted today. Companion
documents, all current: `brock_decision_packet_2026-08-12.md` (his decisions, still unsent),
`BROCK_ASKS_2026-08-12.md` (now through §3.8), `COWORK_DRAFTS_ENG_REVIEW_2026-08-12.md`
(engineering's review of Cowork's drafts), `docs/design/conformance_sweep_2026-08-11.md`
(live acceptance state), `docs/design/round2_delta_inventory.md` (30-row design delta with
keep/drop recommendations), and the external `tyndale_deep_review_2026-08-13.md` (workspace
root) whose 7 findings + 3 nits are **all closed as of today**.

---

## 1 · The scoreboard

| Measure | Value *(re-counted 2026-08-27)* |
|---|---|
| Repo | 396 commits on main; 130 since 2026-08-17 |
| Runtime | FastAPI monolith · 23 route modules · 48 agent/source modules · 47 migrations (0001–0047), chain verified from empty in CI |
| Tests | Runtime: **1,118 collected** (1,110+ passing / 5 skipped) · Mobile: **135 tests / 29 jest suites**, typecheck clean · E2E harness: 22 synthetic scenarios + the record-aggregates check |
| Copy registry | 136 key sections (120 tier-tagged values: 112 `[A]` · 6 `[C]` · 2 `[B]` — the PACE/program handoffs), zero placeholders, drift-guarded; 40 keys boot-gated via RENDER_PATH_KEYS |
| Conformance | 08-11 sweep stands (63 PASS · 4 FAIL · 1 PARTIAL · 6 N-A-YET); B1/B3/C1/C5 checklist rows amended to the 08-18 rulings on 2026-08-27 |
| Decisions | DL-01 – DL-92+ canonical in `docs/decision-log.md` (Cowork numbers new entries as they land) |
| CI | 11 workflows; deploy-runtime now GATES on the reusable Runtime CI suite (2026-08-27); Runtime CI triggers cover the repo-wide guard scans |
| Dev environment | All services healthy on `*.tyndaleapp.net`; 10 Container App Jobs green; qdrant seeded with 19 error-detection rules incl. the golden payer rule |

## 2 · What the product does today (deployed, dev)

A signed-in user uploads bills/EOBs — by file picker or, new this week, **camera capture on
web** (viewfinder, static framing guide, review/retake, multi-page grouping into one
document). Real Azure Document Intelligence OCRs them; a layered classifier types them (bill,
EOB, MSN, MA-EOB, GFE, TRICARE, VA, collections, card, SBC…); typed fields are extracted at
parse time (provider, patient, date of service, and — new — **claim number, account number,
provider phone, payer phone**). The chat-first thread (flag on in dev) runs the case as a
conversation: real-transition status card, ≤3-card encounter verification with free-text
mapping, and the five authored chat states (attest-and-proceed with server-enforced 409 gate,
wrong-document 4-branch redirect, reconcile-first ladder, fabrication + guarantee declines,
PACE handoff). The audit computes the three numbers independently (the EOB can never anchor),
renders findings with a **grounding line on every card** (citation chip or an explicit
no-source state — a bare claim is structurally impossible), suppresses the gap callout on
clean bills, and hands the user a gameplan: biggest-dollar-first call scripts, full-screen
call mode with the party's own reference number pinned (claim# for payer calls, account# for
provider calls) and **tap-to-dial from typed phone numbers only**. "How did it go?" taps now
record at the tap (the outcome-capture denominator), and the dashboard follow-up catches
everyone else. Sub-cases roll up into the Record view. Settings now includes the
**statutory access/deletion request intake** (encrypted event, discloses nothing). The
marketing site carries the full round-2 landing.

## 3 · Shipped since the deep review (2026-08-13 → today) — the delta Cowork hasn't seen

The deep review's verdict was "seven findings, three nits, one overdue environment." The
seven and three are **done, deployed, and each carries a regression guard**:

1. **Flag wiring closed for good.** The 3 orphaned flags (`enable_audit_ready_email`,
   `use_real_crisis_classifier`, `allow_fixture_fallback`) are wired var→env→tfvars, and
   `test_flag_env_wiring.py` introspects every `bool` on Settings against `compute.tf` — a
   new flag with no env block fails CI by name. Four hardening bools are allowlisted with
   written reasons (making them tfvars knobs would turn "weaken security posture" into a
   one-line plan diff).
2. **Crons actually run.** `analytics_rollup` + `nudge` scheduled;
   `test_cron_infra_parity.py` holds registry↔terraform in both directions.
3. **Statutory rights are reachable.** Settings row → screen → the existing encrypted
   intake. The UI holds the no-disclosure invariant (receipt identical whether or not the
   person exists in our data; a jest test asserts no found/not-found language can render).
4. **Call outcomes record at the tap** — idempotent, typed route enum carrying **no money**
   (a test pins the prop set so an amount can't be added without failing), stamping the
   follow-up *recency* clock rather than writing an `outcome_report` (which would have
   retired the real "did it work?" question forever).
5. **Bridge idempotency is real now**: marker honored in `_post` + a partial unique index
   (migration 0039); collisions counted (`bridge_conflicts`) instead of vanishing into the
   blanket except. The old test monkeypatched the very function under test; the new one
   calls it twice against the DB.
6. **Nits:** `DOCTRINE_VIOLATIONS` + `bridge_conflicts` on the admin ops panel; the
   always-true drift-guard assert deleted (with the reasoning left in place); and a
   **render-path key manifest** — staging/prod now refuses to boot if any of the 28 keys the
   thread bridge renders is missing from the registry, so a malformed copy drop fails at
   startup instead of shipping `<MISSING-script>` markers into threads. Dev deliberately
   still boots.

Plus three feature-scale items from the same 48 hours:

- **B4 — typed call identifiers** (migration 0037): claim/account/phones extracted per
  document, promoted to the case by *which party's document type assigns the field*, exposed
  through the gameplan and the registry variable resolver (present-values-only, so his §0
  rule 2 degradation fires on absence). Backfill script exists; **status of its run on dev
  is unconfirmed** — Beloit's `Account # 1821709` in call mode is the live test.
- **N1 — camera-first capture (web)**: honest by construction — no "Looks readable" badge
  (only measured warnings: resolution floor, Laplacian-variance blur), no fake edge
  detection. `assessCapture` has no field that could carry a "pass," and a test holds that
  across the input cross-product. Native is blocked (see §6).
- **The audit-ready email (D3) — live in dev.** Sends on BOTH terminal outcomes (ready, and
  needs-documents — a user who left is waiting either way), never on `system_error`.
  PHI-free by construction (nothing case-specific interpolated; both bodies tested through
  the real DL-47 guard). Exactly-once via a stamp written only after SendGrid accepts.
  Flipping it made **three** authored strings honest at once (§2.2, §2.3 long_wait, §10.3
  cap_collision all promise this email). Found en route: **the nudge cron had never actually
  sent anything** — it logged success without calling SendGrid and stamped its ledger,
  permanently losing each stage. `app/notify/email.py` is now the one send path and returns
  False when nothing was delivered.
- **G6 — the nudge split (today).** His §11.5 +3d/+14d copy is *follow-through* voice, not
  document-chase voice — so the conflated cron became two nudges: the **chase** keeps its
  engineering body (it must name the missing document type), and a new **check-in** renders
  his §11.5 verbatim from the registry on its real premise (audit done + actionable gameplan
  + nothing reported), `{deadline_date}` from persisted deadlines only (degrading to the
  no-variable string, never an invented date, never the in-thread apology in an inbox),
  suppressed once the user reports a call. Chase wins when both premises hold. **Split needs
  Brock's confirmation — asks §3.8.**

## 4 · The invariants, and what enforces them (the part worth trusting)

Every one of these is a mechanism, not a convention — the deep review adversarially
confirmed the first six, and this week added the rest:

| Invariant | Enforcement |
|---|---|
| No fabricated data, ever | Status bars fill on real transitions only; zero-gap suppression; welcome-summary hard rules; capture warns-but-never-claims; `allow_fixture_fallback=false` + prod boot refusal |
| Copy is Brock's, verbatim | Drift guard fails CI naming the key; changes arrive only as new versions of `33_orchestration_script.md` |
| `[B]` never renders uncited | Renderer degrades + `DOCTRINE_VIOLATIONS` counter (now visible on the ops panel) |
| `[C]` never predicts | Fails at boot |
| Unfilled variables never leak | §0 rule 2 degradation + slot-scrub; present-values-only resolver |
| Findings never render bare | `FindingOut.source_line`/`has_source` stamped server-side; card renders chip or honest no-source line |
| Analytics cannot hold PHI | No free-string property type exists; typed enums only; denominators structurally mandatory |
| Audit writes are encrypted | AES-256-GCM envelope on the single write path; key live in dev |
| Recovered ≠ estimated | Confirmed-only tally; call outcomes carry no money by type |
| Email promises are true | D3 line gated on the flag that sends the email; placeholders withheld from copy surfaces; every send through the DL-47 guard; unsent ≠ stamped |
| Flags/crons/keys can't silently orphan | The three new guard tests (flags↔terraform, registry↔crons.tf, bridge-keys↔registry boot gate) — each verified by deletion, each with a guard-the-guard assertion so a broken parser can't pass vacuously |

## 5 · Live dev configuration (tfvars, current)

ON: foundry, real Claude, real OCR, real auth, chat-first audit, record view,
audit-ready email, crisis classifier, all custom domains/certs.
OFF (deliberate): `use_real_presidio` (Phase-4 security cutover), `enable_nsa_checks`
(awaits the 50-state seed gate), `enable_cpt_display` (AMA license), `enable_appeals_casemgmt`,
`enable_nudge_emails` (cron scans and logs; sends dark until flipped), `enable_first_case_unlock`,
`enable_billing`, `enable_coverage_connection`, `allow_fixture_fallback` (never on anywhere real).

## 6 · Not done — the honest ledger

1. **Staging Terraform: zero files.** Third audit in a row. Spec has existed since July 9.
   The deep review's explicit recommendation: *the next session, before anything new.*
   Nothing blocks it but scheduling.
2. **Native camera (iOS/Android).** Blocked by DL-44: `react-native-worklets@0.9.1` peers
   RN 0.83–0.86 against our 0.79.6, so no Expo native package can install. **Nothing in
   source imports worklets** — removal is very likely the whole unblock (~2–4h if it holds,
   an SDK upgrade if not) but needs a verified `npm install` on Phil's machine.
   `isCaptureSupported()` is the single seam.
3. **X2/X3/X5 checkers** — ~~typed stubs that raise~~ **IMPLEMENTED (status refresh
   2026-08-27)**: X3's disclosure tiers are the deterministic `materiality.disclosure_tier`
   ladder in production; X5's error-type derivation runs at the finding READ seam in
   production (`annotate_error_type`, upstream-asserted or derived_draft); X2's
   informational typing renders via the doctrine-config category maps. Still open for
   Brock: the X5 enum blessing + the 3 unmapped payer rule_types (37 draft).
4. **Billing** (E6–E8, I1–I3): dark scaffold by design until the pricing memo.
5. **A8** — mobile body text is 14px against a ≥16px requirement; reflows every screen;
   deliberately not done blind (his call, packet item).
6. **Access-request fulfillment** — intake only; lookup/fulfillment is D2 work with Jonas.
   `access_request_received` analytics event is registered but can't emit (intake is
   unauthenticated; analytics has no anonymous path yet).
7. **Round-2 delta application** — 16 KEEP rows costed and ready; cannot start until the
   veto pass returns.
8. **Smaller:** RD-4 screenshots (task #61) · SMS seam (Twilio decision) · D2 nudge
   fulfillment email copy is engineering-owned (asks §3.7) · `system_error`'s "I'll email
   you when it's working again" promises a recovery email that doesn't exist (packet).

## 7 · Blocked on Brock — the single bottleneck

**The decision packet (`brock_decision_packet_2026-08-12.md`) is still unsent.** Everything
substantial routes through it: A1–A7 sign-offs (the no-base-rate §10.2 variant — the
launch-default guarantee decline currently degrades; eleven unauthored keys rendering
engineering voice; `{itemized_request_script}`; wrong-doc one-vs-four; SUD prompt — which is
also sweep FAIL F2; X-rules — F8's no-base-rate variant included; the 30-row delta pass) and
the B-list judgment calls (crisis-routing vs DL-04; the $504,100 substantiation; headline;
`[B]` tag assignments — sweep FAIL G3; A8). New asks since the packet was written: **§3.6**
capture copy + the no-badge call, **§3.7** the two audit-ready email bodies, **§3.8** the
nudge split confirmation. Engineering's review note
(`COWORK_DRAFTS_ENG_REVIEW_2026-08-12.md`) must ride along — it corrects two stale
dependency warnings in the drafts (B4 shipped; `{claim_number}` etc. now resolve) and flags
the `attest.edge_substance` `[A]`→`[B]` tagging question.

## 8 · Verification posture, including its known blind spots

- Full runtime suite + ruff green locally and in CI; migrations round-trip on fresh DBs;
  guard tests verified by deletion.
- **Mobile is verifiable on this machine now** (no node on PATH, but VS Code's Electron runs
  tsc/jest via `ELECTRON_RUN_AS_NODE=1`) — what it does NOT give is npm, so lockfile
  changes/installs still need Phil.
- Known blind spots, each already bitten once and now documented: local pytest doesn't run
  `alembic check` (models↔migrations drift only fails in CI); the design-token guard's
  workflow is path-filtered to `runtime/**` while the test scans `apps/**` (chip open to
  widen it); local shared-DB rate-limit flakes are cured by aging rows 25h and are not CI
  signals.
- One unconfirmed deploy-side item: **the B4 backfill run on dev** (dry-run then real);
  until it runs, pre-B4 cases show no call identifiers.

## 9 · Recommended sequence from here

1. **Staging Terraform session** (July 9 Phase-3 spec) — the standing organizational debt;
   every launch path runs through a staging rehearsal, and the boot gates
   (placeholder-free + render-path manifest) now give staging something real to verify.
2. **Send the packet** (with the eng review note) — unblocks X-rules checkers, the
   16-row delta application session, eleven strings, and four sweep FAILs in one motion.
3. **Worklets removal experiment** (1h timebox on a machine with npm) — likely unblocks
   native camera and every future Expo package.
4. On packet return: **X2/X3/X5 checkers** + **delta application session** + copy drop v2
   (drift guard makes the drop mechanical).
5. Flip-when-ready: `enable_nudge_emails` (both nudges are real now and PHI-guarded);
   Presidio cutover per the Phase-4 security track.
