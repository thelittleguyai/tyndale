# Dev Test Day — the ordered walkthrough

*Written 2026-08-17 (Dev-Complete item 7). For Phil, testing the deployed dev environment
in a real browser. Everything here is doable in one sitting; §0 is the night before.*

The product app is **https://app.tyndaleapp.net**, the API is **https://api.tyndaleapp.net**,
admin is **https://admin.tyndaleapp.net**. Dev runs the full real pipeline (real auth, real
OCR, Foundry Claude, fixture fallback off), so everything below is the true product path.

---

## 0 · Night before

### 0.1 Deploy this branch
`git push` + your normal `terraform apply` in `infra/envs/dev`. Migrations **0040**
(recovery-email stamp) and **0041** (nullable analytics user) ride the deploy as usual.

### 0.2 Flags for the day (`infra/envs/dev/terraform.tfvars`)

| Flag | Today | For test day |
|---|---|---|
| `enable_chat_first_audit` | true | leave on |
| `enable_record_view` | true | leave on |
| `enable_audit_ready_email` | true | leave on — gates audit-ready, needs-docs, recovery emails **and** the §2.2/§10.4 promise lines |
| `enable_nudge_emails` | false | **flip true** if you want to exercise the chase / check-in crons |
| `enable_first_case_unlock` | false | **flip true** to see the unlock moment on a fresh account |

### 0.3 Verify the deploy took
Admin → System, or `GET /v1/admin/system/health`: `deploy_sha` matches your pushed HEAD;
`anthropic_status`, `qdrant_status` healthy; `last_claude_call` recent and ok.

### 0.3b Pin warm replicas for the test window
In `infra/envs/dev/compute.tf`, set `min_replicas = 1` on the **runtime** app (line ~108)
and the **app** container (line ~1089), then apply. These are hardcoded in compute.tf, not
tfvars. Scale-to-zero cold starts read as hangs during a hands-on walkthrough (observed
live 2026-08-17 — a first request after idle sits through container boot). Revert after
test day if you want scale-to-zero back.

### 0.4 B4 backfill (typed call identifiers on existing cases)
From `runtime/` with `DATABASE_URL` pointed at the dev database (same connection pattern as
the provider-name backfill):

```bash
uv run python scripts/backfill_call_identifiers.py --dry-run
```

then again without `--dry-run`. **Acceptance check:** open the Beloit case → call mode reads
an account number that matches the paper bill. A case with no structured source keeps NULLs
and the call script degrades — that is correct behavior, not a bug.

### 0.5 The e2e sweep (the last leg of the ready-to-test gate)
Run the full harness against dev **after** the apply, so the X2/X3/X5 contract assertions
run against the build that has the `error_type` read seam:

```bash
export TYNDALE_E2E_SECRET="$(az keyvault secret show --vault-name tyndale-dev-kv-71izsy --name e2e-test-token-secret --query value -o tsv)"
```

```bash
cd runtime && uv run python scripts/e2e_scenarios/run_scenarios.py --dev --chat-first --record
```

Expect **23/23** (22 scenarios + the record-aggregates row). Costs ~22 real audits; runs
~45–90 min as an isolated synthetic user (`…@e2e.tyndale.test`) — it never touches your
account or the Beloit case. If a late scenario 429s on upload (20/hr cap), wait out the
window and rerun just it with `--only <name>`.

> Why not local: the local runtime is the stub pipeline by construction (no DI, no Qdrant
> corpus, fixture extract), and the harness's fixture-marker tripwire fails it by design.
> The sweep is only meaningful against a real pipeline — dev.

### 0.6 Synthetic bills for manual uploads
```bash
cd runtime && uv run python scripts/e2e_scenarios/run_scenarios.py --generate-only
```
Prints a folder of synthetic PDFs (duplicate line, unbundled panel, summary-only bill,
EOB-only, unreadable, not-a-bill…). Upload these by hand during the walkthrough — no real
PHI needed beyond your own Beloit documents.

### 0.7 Prep
A second browser profile (or your phone's browser) for the fresh-account path — dev sends
real magic-link email. Have your inbox open all day; emails are part of the test.

---

## 1–10 · The walkthrough

Do these in order on the fresh account (switch to your main account where marked). Check
each box; anything that fails, capture the `case_file_id` (§ "If something breaks").

### 1 · Upload (fresh account)
- [ ] Camera leads on the upload screen; file picker is the alternative, not the default (N1)
- [ ] Web capture: live viewfinder, static guide frame, **no "Looks readable" badge** —
      keep/retake is your judgment; a too-small capture warns, never blocks
- [ ] Multi-page: take 2+ pages, "Done — N pages" sends them as one document
- [ ] Upload a `.txt` or random file → clean **422**, honest not-a-bill copy on a real-but-
      wrong doc (P1)
- [ ] Upload the unreadable synthetic PDF → honest degraded state, no invented line items

### 2 · Thread (chat-first)
- [ ] Status header: "Working on your audit" + spinner while running; "Audit ready" ✓ at
      terminal (L1)
- [ ] Moment cards show the context line (provider · payer) when known (L2)
- [ ] Three-numbers moment: billed / EOB says / Tyndale computes, tabular figures (L3) —
      and the EOB's number is never presented as the answer
- [ ] **Gap callout renders** when a finding has one (E3 — new this build; it never rendered
      before)
- [ ] Branch cards: summary-bill upload → "Add the itemized bill"; blurry page →
      "Add a clearer photo"; wrong doc → "Add your bill or EOB"; conflicting totals →
      reconcile card with **no** action button (N2/F3/F4)

### 3 · Encounter verification
- [ ] Each charged line in plain language; option buttons carry the ✓/✗/? icons (L5)
- [ ] Free-text works: type "I never got that scan" → mapped suggestion to confirm, never
      silently applied (PB)
- [ ] Name-mismatch doc → attest-and-proceed state, not a dead end (CS1)

### 4 · Reveal
- [ ] Findings state what was computed vs what was claimed, with source lines (E4/H3)
- [ ] No outcome predictions anywhere — genuine uncertainty is named, not hedged

### 5 · Gameplan + call mode (main account, Beloit case)
- [ ] Gameplan steps are concrete and ordered
- [ ] Call mode quotes claim / account / phone from **typed fields** (B4) — matches the
      paper bill; a case without them degrades the script instead of quoting a guess
- [ ] Tally line: 26px tabular figures (L6)

### 6 · Outcome
- [ ] Log an outcome; the follow-up card sits **above** coverage metrics on the dashboard (B5)
- [ ] Metric cards: 26px semibold tabular numbers (N5)

### 7 · Tyndale Record
- [ ] Rows titled provider + date of service, not status jargon
- [ ] Aggregates honest: $0 recovered shows as $0, never inflated or hidden
- [ ] Sub-case summary (`/case/{id}`) matches the thread's terminal state

### 8 · Settings + theme
- [ ] Toggle light/dark — body text is 16px and reads comfortably in both (A8); compare
      against `docs/design/screenshots/` if unsure
- [ ] **Notifications** (2026-08-19 item 1): the email toggle is REAL — flip it off, trigger
      the nudge cron from Admin → zero reminder sends for this user and the ledger stays
      unstamped (flip back on later → the same stage still sends). Transactional mail
      (audit-ready, magic links) ignores the toggle. SMS still reads "Coming soon"
- [ ] **State of residence** (item 2): set it (two-letter code validates); on an account
      whose documents carry a patient state, the suggestion chip offers it — never
      silently set. Mailing address folds away under a disclosure
- [ ] **Coverage type** (item 3): the row is tappable → the same 7-population ladder from
      intake, detected candidate preselected; confirming writes through the existing
      user-confirmed path and the row updates on return
- [ ] **Secondary coverage** (item 4): shows what intake captured (hint) when no row;
      add insurer / member ID / plan type (chips); card photos front + back store as
      secondary sides and never touch the primary card merge; two-tap Remove clears
      row + photos
- [ ] **Plan documents** (item 5): upload the synthetic SBC once → "SBC on file" chip;
      a stalled needs-documents case whose only gap was the SBC re-runs by itself;
      the unlock-more checklist on OTHER cases shows the SBC line checked
- [ ] Sign out / magic link back in

### 9 · Access request
- [ ] Settings → access request: submit; receipt is identical regardless of what exists
      (anti-enumeration — the stub confirms receipt and discloses nothing)
- [ ] (Optional) the `access_request_received` analytics row lands with **no** user attached
      — covered by tests; spot-check in the dev DB only if curious

### 10 · Admin pass
- [ ] Dashboard panels populate; numbers are n/d pairs, not bare percentages
- [ ] System page: no unexplained `recent_errors`, `system_alerts` count matches reality
- [ ] Crons page: trigger `nudge` → clean run log. Zero sends is a PASS unless a case is
      ≥3d in `needs_documents` (chase) or ≥3d past `audit_complete` (check-in) — content
      is test-covered; the cron-run plumbing is what you're checking
- [ ] Case provenance view on one of today's cases: extraction truth surfaced, no fixture
      markers

---

## Emails you should see today
1. **Magic link** (sign-in, fresh account)
2. **Audit ready** (terminal on a completed case) — no PHI: no amounts, providers, or claim
   numbers, ever (DL-47)
3. **Still need a document** (terminal on a needs-documents case — upload the EOB-only
   synthetic)
4. **Chase / check-in nudges** — only if `enable_nudge_emails=true` **and** a case is aged
   ≥3d into the qualifying state; otherwise N/A today, verified by tests
5. **Recovery email** (§10.4) — *not stageable honestly* (needs a real `system_error` that
   later completes). Verified by tests; skip on test day.

## Known-cosmetic — do NOT file these
- **Held for Brock (packet pending):** the 4 delta conflicts, N7, crisis-routing decision,
  and all `[B]`-tag copy. Conformance sweep FAILs **F2 · F8 · G3** and PARTIAL **C5** are
  all in this bucket.
- **Engineering-voiced copy awaiting the packet:** some thread strings render engineering
  seeds (UNMAPPED provenance — e.g. the no-email system-error line, needs-docs email body,
  chase nudge body). They read fine but aren't Brock's final voice. Don't file voice bugs.
- **Native camera** is a phone **dev-build** test, not a browser test — the browser gets
  the web capture path. The native file picker (expo-document-picker) is a known small
  follow-up; the native upload screen says so.

## If something breaks
Grab the `case_file_id` (URL or admin → Cases), check admin → System `recent_errors` and
the case's provenance view, note which walkthrough step, and file it with those three
things. Don't retry uploads in a loop — the 20/hr upload cap will make a second problem.

---

## §local-build — reproducing the screenshots / running the app locally

How the A8 before/after screenshots in `docs/design/screenshots/` were made, and the
general local recipe (no Docker needed):

1. **Runtime** (stub auth, stub pipeline — UI-faithful, audit-fake):
   `cd runtime &&
   DATABASE_URL="postgresql+asyncpg://tyndale:tyndale@127.0.0.1:5432/tyndale"
   ENABLE_CHAT_FIRST_AUDIT=true ENABLE_RECORD_VIEW=true
   CORS_ALLOWED_ORIGINS="http://localhost:8081" COOKIE_DOMAIN="" COOKIE_SECURE=false
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`
   For harness-speed local runs add `RATE_LIMIT_ENABLED=false` (the test suite does).
2. **Web build** (any Node ≥22): `cd apps/mobile &&
   EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npx expo export --platform web
   --output-dir dist-a8` (build dirs stay uncommitted).
3. **Serve with SPA fallback** — plain `http.server` 404s dynamic routes; any static server
   that rewrites misses to `index.html` works:
   ```python
   # serve_spa.py <dist-dir> <port>
   import http.server, functools, os, sys
   root = sys.argv[1]
   class H(http.server.SimpleHTTPRequestHandler):
       def send_head(self):
           p = self.translate_path(self.path)
           if not os.path.exists(p): self.path = "/index.html"
           return super().send_head()
   http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])),
       functools.partial(H, directory=root)).serve_forever()
   ```
4. **Profile gate:** a fresh stub user redirects to onboarding until the profile is
   completed — `PATCH /v1/profile` with `{"accept_terms": true, …}` (the field is
   `accept_terms`, not `terms_accepted`).
5. **Screenshots:** playwright-core + system Chrome; dark mode = `colorScheme` emulation
   **plus** localStorage `tyndale.theme_mode`. Theme both ways before judging contrast.
