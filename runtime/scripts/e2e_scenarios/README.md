# E2E bill-scenario harness (HP-2)

Systematic, synthetic end-to-end coverage of the audit pipeline: upload → extraction → encounter
verification → audit → terminal state. Replaces manual PDF uploads (two manual cases already
surfaced six production bugs).

**Synthetic identities only.** Every patient/provider/account is fabricated (`generate_docs.py`).
Never put real PHI here.

## Pieces

- `generate_docs.py` — reportlab PDF templates (bill, EOB, MSN, collections, garbage), parameterized.
- `scenarios/*.json` — declarative scenarios: documents to generate, encounter answers, expected
  terminal state + finding types.
- `run_scenarios.py` — the driver: per scenario, upload → poll extraction → answer encounter →
  run audit → poll to terminal → assert terminal + finding types + **no fixture markers**. Prints
  a pass/fail table with `case_file_id` on every failure (inspect it in the admin console) and
  per-stage timings.

## Running

```bash
# local docker-compose (the dev auth stub makes every request the dev admin user)
uv run python scripts/e2e_scenarios/run_scenarios.py

# the deployed dev API — needs an admin session token to mint the synthetic user
TYNDALE_ADMIN_TOKEN=<admin session token> \
  uv run python scripts/e2e_scenarios/run_scenarios.py --dev

# a subset, or just regenerate the PDFs
uv run python scripts/e2e_scenarios/run_scenarios.py --only duplicate_cpt_line
uv run python scripts/e2e_scenarios/run_scenarios.py --generate-only

# also assert the chat-first thread / the Tyndale Record match engine state (DL-91). Each flag
# needs its server flag on: --chat-first → ENABLE_CHAT_FIRST_AUDIT, --record → ENABLE_RECORD_VIEW.
uv run python scripts/e2e_scenarios/run_scenarios.py --chat-first --record
```

Auth uses the **dev-only** `POST /v1/admin/test-token` endpoint (404s in production; rejects any
non-`@e2e.tyndale.test` email), authorized by EITHER:

- **`TYNDALE_E2E_SECRET`** (preferred) — the stable Key Vault shared secret, sent as the
  `X-E2E-Test-Secret` header. Never expires. Retrieve with
  `terraform output -raw e2e_test_token_secret` (dev env) and store it as the GitHub repo secret
  **`E2E_TEST_SECRET`**.
- **`TYNDALE_ADMIN_TOKEN`** (fallback) — an admin session token (a 7-day JWT; needs refresh).

Local runs (`run_scenarios.py` without `--dev`) need neither — the dev-user stub is already admin.
CI: the `E2E Scenarios` workflow (`workflow_dispatch`, never scheduled — real Claude token cost)
runs against dev using those repo secrets.

## Cost

Each scenario runs a real audit on dev (multi-minute, real Claude tokens). ~12 audits per full
run. Trigger on demand, not on a schedule.
