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
  run audit → poll to terminal → assert terminal + finding types + **no fixture markers** (`02417` · `05821` · `Z4411` — structurally unassigned codes; a hit in Bill Detective `facts.notes` that is genuine family reasoning about a code on the bill is LEDGERED, everything else trips). Prints
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

## Retrieval is asserted, not assumed (2026-09-23)

A scenario with `"expects_retrieval": true` FAILS when the audit's own retrieval record
(`audit_provenance.retrieval` on `/v1/audit/{id}`) shows any knowledge-tool call errored, or
none was made. The 2026-09-18 sweep reported 22/23 green while every `qdrant_search_*` call
was failing (Voyage 429 / rerank 400) — that was a harness gap, not a pass. Every scenario that
completes a real audit carries the flag; `s07_knee_arthroscopy` (the 2026-09-23 specimen shape)
carries it too. When Voyage is unhealthy the sweep goes red and says so — that is the point.

## A throttled provider is asserted, not hoped about (e2e re-test 2026-09-23)

A scenario with `"fault": "<name>"` sends it as the `X-Tyndale-Fault` header on the upload that
opens its case. The runtime honours it ONLY for a synthetic user outside staging/production and
only for a known fault (`app/faults.py`); anywhere else the header is ignored. Today there is one:
`claude_429:lead_planner` — every attempt of the Lead Planner's summary call gets a 429, so the
backoff runs for real and gives up. `s07_knee_arthroscopy_summary_429` asserts the run still
finishes `audit_complete` with its findings and three numbers and the summary OWED
(`"summary_pending": true` — the flag plus the registry notice for the summary slot), never
`system_error`. It does not assert retrieval (that is s07's job, and it stays red while Voyage is).

## Two front doors (doc 40, 2026-09-21)

A scenario with an `"intake"` block is driven through the GUIDED route — `POST /v1/intake/start`,
then the harness reads the planner's `screen` and reacts to it exactly as the app does: it
uploads where the scenario maps files to a capture screen (`intake.uploads`), answers where it
has an answer (`intake.answers`), skips what it is told to (`intake.skip`), and FAILS if the
planner raises a screen the scenario has no answer for. What it asserts is the planner:
`expect_never` (screens this case already answers — a card that named the payer must not raise
`insurer`), `expect_screens` / `expect_final` (`READY` → `POST /v1/intake/run` → the shared audit
and the usual `expect` block; or `handoff`), and that every finding names a side (§C14).

A `handoff` ending is FOLLOWED, because it is an exit and not a parking spot: the harness calls
`POST /v1/intake/handoff` and fails unless the route it names is one of chat-first's own entry
points for that case, the landing no longer offers the case as "pick up where you left off", and
a second call returns the same route. The harness never calls the card-extract step either — the
planner reads a new card itself, so a card that names the payer must still never raise `insurer`.

Run them with **`--intake-mode guided`** (workflow input `intake_mode`, default `guided`); without
it they are reported as skipped. No server flag is involved: a case opened through
`/v1/intake/start` records `intake_mode='guided'` by construction, so both routes land in the
same Human Review queue. They need the REAL pipeline — locally the stub OCR types every upload
`unclassified`, and the planner (correctly) keeps asking for a bill. Today:
`guided_intake_commercial`, `guided_intake_noncommercial_handoff`.

## A sweep, end to end (2026-09-18)

**Duration.** A full sweep is **~80 minutes** — 23 scenarios, each a multi-minute real audit —
and the job is capped at **150 minutes** so a stalled run can never sit for GitHub's 6-hour
default. Run a subset with `--only` (workflow input `only`) when you don't need all of it.

**Identity — one synthetic user per run AND per attempt.** Each run authenticates as
`e2e-runner+<run id>-<attempt>@e2e.tyndale.test` (a UTC timestamp locally). The 20-uploads/hour
cap is per identity, so runs don't inherit each other's spend — and because "Re-run jobs" keeps
the run id, the attempt is part of the tag too. Every report prints the identity. Override it
with **`E2E_SYNTH_EMAIL=<address>`** (workflow input `identity`) to act as a *previous* run —
cases are owner-only, so that is the only way to `--inspect` its cases or finish its teardown.
Synthetic identities are refused by the human-review queue: a sweep never lands in a
reviewer's list.

**Rate limits.** A full sweep grazes the upload cap near the end. A 429 is waited out once per
upload (`Retry-After`, ≤ 15 min), from a **30-minute per-run budget**; past it the run stops
at the next scenario boundary with the remaining scenarios reported `SKIP` — a clean summary
instead of sleeping toward the hard kill.

**Deploy interlock — the sweep yields.** A dev runtime deploy swaps the Container App revision
and kills in-flight audits, so the two must not overlap — and a deploy must never wait or be
dropped. The harness watches the `deploy-runtime` workflow through the Actions API
(`GITHUB_TOKEN` + `actions: read`, provided by the workflow): it waits up to 20 minutes for an
in-flight deploy before uploading anything, re-checks at **every scenario boundary**, and if a
deploy has begun it stops — report, teardown, **exit code 3**, a warning annotation — for you to
re-dispatch once the deploy is done. Nothing that ran is marked failed by a yield. Locally (no
token) the interlock is off, and it fails open on an API error. Two things it cannot see:
`terraform apply` (it rolls the runtime too — don't apply mid-sweep) and a scale-to-zero cold
start, which the preflight absorbs (it warms `/health` with retries and retries a 5xx on
`test-token`, the 30–60 s cutover after a deploy "completes").

**Teardown.** `--cleanup` removes the run's identity at the end through the dev-only
`POST /v1/admin/test-cleanup` — cases, stored documents, threads, findings, review rows,
feedback, analytics; never the audit log. It is gated exactly like `test-token` (404 in
production and without the shared secret / an admin session) and refuses any address without
the synthetic suffix, as does the harness before it even calls. **FAILED scenarios' cases are
kept** — and therefore the identity — so forensics still work:

```bash
gh workflow run e2e-scenarios.yml -f identity=<address> -f inspect=<case_file_id>[,<id>…]
gh workflow run e2e-scenarios.yml -f identity=<address> -f cleanup_only=true   # finish it
```

The workflow passes `--cleanup` on the run and then runs `--cleanup-only` in an `if: always()`
step as the safety net for a crash, a timeout or a cancel; both honour the keep list the run
wrote, and an `inspect` run never tears anything down.

## Cost

Each scenario runs a real audit on dev (multi-minute, real Claude tokens). ~22 audits per full
run, ~80 minutes. Trigger on demand, not on a schedule.
