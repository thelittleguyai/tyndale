# Go-live checklist (pre-launch confirmations)

Companion to `SECURITY_GO_LIVE.md` (the security/config gates). This file holds the
**content and substantiation** confirmations that must be true before a public launch.
Nothing here creates or touches staging/production infrastructure.

## Substantiation — public figures on the landing page

- [ ] **$504,100 "recovered for members" (B4)** — *stays on the page per Brock 2026-08-18
      (B2).* Owed before launch: a **substantiation entry + as-of date (Brock)** in the
      analytics substantiation file, naming what the figure counts, the period, and what
      updates it. A public dollar figure next to a "we're early" beta band needs a paper trail.
- [ ] **C1 / C2 citations (Brock)** — the two landing claims still held for a source (the
      "$400 dispute right" tip among them) ship only with their citations.
- [ ] **B11** — the page never claims "80% of medical bills contain errors" (banned,
      unsupported). CI grep stays clean.

## Ops readiness (B2 — the alert path)

- [ ] **Someone is paged on `alerts`.** `GET /v1/admin/system/health` now carries ONE alert
      list (Admin › System › "Needs a person"): `retrieval_degraded` (last-50 knowledge-tool
      error rate ≥ 20%, with the last Voyage status per endpoint), `cron_failed` (any cron run
      that did not succeed in the last 7 days — `cms_ncd_lcd_bulk` failed on 2026-09-19 and
      nothing surfaced it), and `system_error` (audits that told the user "the team has been
      notified"). The runtime also logs `retrieval.degraded` on the transition, for a Log
      Analytics alert rule. Owed before launch: the rule + the person it reaches.

## Copy gates

- [ ] Orchestration script at the signed-off version (v1.1 as of 2026-08-18); zero
      `[PLACEHOLDER-eng]` values (`tests/test_orchestration_script.py` pins it; the staging
      boot refuses otherwise).
- [ ] Inbound copy from Brock landed or explicitly held: A4 four-branch wrong-document
      strings, D5 clean-bill/negotiation copy, A6 error taxonomy + §3.10, §3.8 nudge-split
      confirmation.

## Data activation

- [x] Priors tranche 1 received (`intelligence-layer/reference/priors/`) — *2026-08-27:
      5/7 entries LIVE (deductible_amount, oop_max_amount, coinsurance_percent, copay_pcp,
      copay_specialist); copay_er + household_income remain dark BY DESIGN (no defensible
      prior yet — the tranche says so explicitly and the loader keeps them point-form).*
- [ ] 50-state NSA seed + rules/laws corpora content (Brock's program) — balance-billing
      check + retrieval quality.

## Human Review — queue policy (doc 39 §1 + §7-2d) · added 2026-09-21

Six flags decide what a human looks at. All six are wired to the runtime **and every cron**
(the derived env-parity test fails if a tfvars flip would reach one and not the other — a
cron-healed case enqueues through the same policy). Defaults are Brock's §7-2d ruling: review
everything, every trigger on.

- [ ] **`REVIEW_SAMPLE_PCT`** (default `100`) — confirm the launch value **with Brock**. This is
      only the env DEFAULT: a dial an admin saved on the Review page lives in `admin_settings`,
      **overrides it, and survives deploys**. Read the value in force from the Review page (or
      `GET /v1/admin/review/settings`: `review_sample_pct` vs `env_default_pct`) — not from tfvars.
- [ ] **`REVIEW_TRIGGER_FIRST_CASE`** = `true`
- [ ] **`REVIEW_TRIGGER_LOW_CONFIDENCE`** = `true`
- [ ] **`REVIEW_TRIGGER_SYSTEM_ERROR`** = `true`
- [ ] **`REVIEW_TRIGGER_CANARY`** = `true`
- [ ] **`REVIEW_TRIGGER_MATERIAL_DISAGREEMENT`** = `true`
      — the five always-enqueue triggers fire regardless of the dial. Turning one off removes a
      class of runs from human eyes whenever the dial is below 100; that is Brock's call. If one
      is off at launch, write who decided and when on this line.
- [ ] **Reviewers exist** — Brock and Phil are `user_type=admin` in the launch env and can each
      open `/review` from an allowlisted IP (§7-2e: the two of them, no assignment machinery).
- [ ] **Capacity** — at dial 100 every completed run is a review row. Agree the expected daily
      volume is reviewable by two people, or set the dial; an unreviewed backlog is visible on
      the health strip ("awaiting review" + median age) but nothing pages on it yet.
