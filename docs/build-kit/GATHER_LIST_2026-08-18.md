# Gather list — keys, variables, and copy the team owes dev

*2026-08-18. What surfaced these: the first two full e2e sweeps against dev (4/23 → 17/23
after the rung-2 completion work) plus the dev-test-day prep. Each item names its owner,
where the value goes, and what breaks while it's missing. No secret values appear in this
document — everything lands in terraform.tfvars (gitignored), Key Vault, or Brock's
authored files.*

---

## Phil — do today (blocks test day)

### 1. SendGrid — RESOLVED to an account-protection issue; one confirmation left
The sweep's `notify.send_failed status=401` (~15× in 45 min) was chased end to end on
2026-08-18. **Everything checks valid**: the tfvars key answers 200 with full scopes, Key
Vault matches tfvars exactly, and — verified by exec probe inside the running container —
the container holds the **identical** key (hash-compared) and SendGrid accepts it from the
container's own egress. The failures were real at the time, on the send endpoint only.

**Best-fit diagnosis:** the sweep fired ~15 emails at `…@e2e.tyndale.test` — a reserved
TLD that can never deliver — in under an hour. That is a textbook spam-trap signature, and
SendGrid pauses mail-send (401) when its fraud review trips.

- **Fixed in code (`93ad148`, deployed):** product emails to the synthetic e2e suffix now
  short-circuit before any network call — sweeps will never again fire real sends.
- **Remaining check (Phil, 1 min):** request a magic link to your real address from the
  dev sign-in screen. Link arrives → account healthy, item closed. Nothing arrives →
  check the SendGrid dashboard for an alert/compliance banner (Activity feed will show
  the 401-era attempts) — that's a SendGrid-side unpause, not a config change.
- While in SendGrid anyway: confirm the `sendgrid_from_email` sender identity is verified.

### 2. Warm replicas for the test window
Scale-to-zero cold starts read as hangs in a hands-on walkthrough (observed live).

- Edit `infra/envs/dev/compute.tf` — hardcoded there, NOT tfvars:
  `min_replicas = 1` on the **runtime** app (~line 108) and the **app** container
  (~line 1089) → apply. Revert after test day for scale-to-zero cost.

### 3. Optional flag: `enable_nsa_checks`
The balance-billing scenario now completes but produces no balance-billing finding —
detection likely sits behind `enable_nsa_checks`, currently **false** on dev. Flip true in
tfvars if you want that scenario exercising; engineering will confirm the gating either way.

---

## Brock — the copy and data only you can supply

### 4. Two registry keys that BLOCK the staging boot (asks §3.11)
The audit now completes at the achievable rung; a completed audit with missing coverage
terms shows the have/need checklist as an *unlock*, not a gate. That state has no authored
voice yet — two keys render `[PLACEHOLDER-eng]`, and the **staging boot refuses to start
until they're authored** (the deliberate forcing function). Nothing else stands between
the script and staging.

- `unlock_more.intro` — eng seed: "Your audit is done — and one more document would
  sharpen it. Add your plan's SBC and I can pin down the cost-sharing math exactly
  instead of ranging it."
- `unlock_more.item_hint` — eng seed: "Already checked items are on file — anything
  unchecked deepens what I can verify."
- Voice guidance engineering followed pending you: completion first, invitation second,
  zero "unfinished" framing.

### 5. The researched priors table — **promoted to user-visible**
`missing_data_priors.py` still carries placeholder low/base/high values
(`missing_data_spectrum_2026-07-03.md` is the pending drop). This was internal machinery;
as of the rung-2 change it is **load-bearing on screen**: the ranges users see ("between
$X and $Y until I see your deductible") are computed from these numbers. Real priors =
honest ranges.

### 6. Earlier asks, still open
- **§3.9** — approve/author the recovery-email body + the `system_error_no_email` trim.
- **§3.10** — one grounding line for `lineitem_plain_language.md` ("never substitute a
  code from these examples"); the sweep showed example bleed can reach audit prose too.
  Keep 70553/A9579/36000 as your example codes — they are the leak-canary set
  (see `intelligence-layer/prompts/README.md`); if you swap them, tell engineering.
- **A6** — sign-off on `doctrine_config.py` (the DRAFT error-type enum, category
  mappings, informational categories). Also wanted from A6: the category taxonomy —
  agents currently mint free-form all-clear phrasings (`diagnostic_audit_clean`,
  `coverage_math_audit`, …) that no fixed list can chase.

---

## Jonas / engineering — provisioning and code, no credentials

### 7. Qdrant collections — RESOLVED to a bigger gap than logged, schemas now in place
The log line (`Collection payer_policies doesn't exist`) undersold it: dev had only ONE of
the four collections (`billing_codes`). Phil's in-container init (2026-08-18) created the
other three — `error_detection_rules`, `laws_regulations`, `payer_policies` — meaning
every dev audit to date ran with rules/laws/payer retrieval hitting NONEXISTENT
collections (tool errors, not even empty results). That context belongs next to every
past judgment about detection quality.

Now: the schemas exist, so retrieval degrades honestly (empty results) instead of
erroring. **The corpora are still empty** — ingestion is content-dependent (Brock's rules
and laws drops + the ingestion runs; Jonas). Two Jonas-side notes from the same session:
qdrant-client 1.18.0 vs server 1.12.4 is outside the supported version skew (pin the
client or upgrade the Qdrant image), and collection creation outlived the default client
timeout — the dev Qdrant container may be resource-starved enough to matter for retrieval
latency too.

### 8. Pre-flip blockers for the 1up wrapper (parked — gated off, not test-day)
- **1up sandbox credentials** (`ONEUP_CLIENT_ID` / `ONEUP_CLIENT_SECRET`) into the
  wrapper's env when the coverage-connection work resumes. The wrapper boots fine without
  them and `/health` reports `configured: false` truthfully.
- **Postgres-backed TokenStore** — the in-memory store loses payer tokens on every
  restart (pinned in the new test suite's name: "RESTART LOSES EVERYTHING").
- **`OneUpApiError` message hardening** — the upstream body (which can carry patient
  identifiers) is embedded in `error.message` today; codified as a visible TODO in the
  wrapper suite. Both must land before `ENABLE_COVERAGE_CONNECTION` flips on for real reads.

---

## Already in hand — nothing to gather

E2E harness secret (GitHub `dev` environment) · `WRAPPER_AUTH_TOKEN` (Key Vault) ·
Azure Document Intelligence · Foundry (managed identity) · `AUDIT_LOG_ENC_KEY`
(the open item there is a re-verification *run* of `verify_audit_encryption.py`, not a key).
