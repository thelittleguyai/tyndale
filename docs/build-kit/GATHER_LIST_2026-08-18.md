# Gather list — keys, variables, and copy the team owes dev

*2026-08-18. What surfaced these: the first two full e2e sweeps against dev (4/23 → 17/23
after the rung-2 completion work) plus the dev-test-day prep. Each item names its owner,
where the value goes, and what breaks while it's missing. No secret values appear in this
document — everything lands in terraform.tfvars (gitignored), Key Vault, or Brock's
authored files.*

---

## Phil — do today (blocks test day)

### 1. SendGrid — **product email is down on dev, but the key is NOT the problem**
The sweep caught it live: `notify.send_failed kind=audit_ready status=401` (~15 times over
45 min). Diagnosis so far (2026-08-18): the tfvars key is **valid** (SendGrid answers 200
with full scopes when tested from a laptop), Key Vault **matches tfvars exactly**
(`terraform plan`: no changes; KV version dated 2026-05-29), the env wiring is correct
(`SENDGRID_API_KEY` ← KV ref), and IP Access Management is **off**. Yet a revision
provisioned the same day got 401 — so the fault is between Key Vault and the running
container (a stale resolved secret) or in the container's egress path.

- **Next step (needs a TTY, 30 seconds):** exec into the runtime container and test the
  key it actually holds, from its own network position:
  ```
  az containerapp exec -n tyndale-dev-runtime -g tyndale-dev-rg --command bash
  # then inside:
  printf %s "$SENDGRID_API_KEY" | wc -c
  curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $SENDGRID_API_KEY" https://api.sendgrid.com/v3/scopes
  ```
  `200` + length 69 → key fine in-container, investigate the send path; `401` or a
  different length → the container holds a stale/dead value: restart the revision
  (`az containerapp revision restart`) so the KV reference re-resolves, and retest.
- Until green, **no product email sends on dev**: audit-ready, needs-docs, nudges, recovery.
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

### 7. Qdrant `payer_policies` collection is missing on dev
Caught live in runtime logs: `Collection payer_policies doesn't exist`. Payer-side
grounding is degraded until `init_collections` + its ingestion run on dev. Plausibly part
of the balance-billing detection miss.

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
