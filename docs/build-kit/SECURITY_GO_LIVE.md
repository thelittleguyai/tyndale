# Security go-live checklist

Source: `tyndale_security_review_2026-08-19.md` (workspace root). The unilateral hardening
items from that review shipped 2026-08-19 (HIGH-1, MEDIUM-2/-5/-6/-10, LOW-14, storage-name +
pin hygiene — see the `fix(security)` commits). What remains is **operator confirmation** at
each launch gate. The boot guard enforces most of this mechanically; this list is the
human double-check.

## Before ANY public env serves real users (staging or production)

- [ ] **`USE_REAL_AUTH=true`** — the seeded-admin stub resolves every request to an admin
      with no sign-in. The boot guard now refuses a staging/production boot without it
      (HIGH-1), and refuses `ALLOW_FIXTURE_FALLBACK=true` in the same envs. Confirm the
      tfvars anyway: the guard protects `NODE_ENV∈{staging,production}` — an env
      mislabeled `development` with public ingress would sidestep it.
- [ ] **`ADMIN_ALLOWED_IPS` non-empty** — empty means NO IP restriction on the admin
      surface. Set it to the real operator IPs before PHI.
- [ ] **`AUDIT_LOG_ENC_KEY` set** (base64 32-byte) — without it, PostToolUse audit payloads
      store as clear-text JSON. Verified wired in dev; confirm per env. Production only
      *warns* on a missing key today (`warn_missing_in_prod`) — check the box by reading
      the boot log, not by assuming.

Also true by construction now, no action needed: verbose 500 bodies are hard-forced off in
staging/production regardless of `DEBUG_ERROR_RESPONSES` (MEDIUM-6); magic-link `return_url`
is same-origin-relative or ignored (MEDIUM-2); the unauthenticated access-request intake has
a dedicated 5/hr/IP window (LOW-14).

## Before `ENABLE_COVERAGE_CONNECTION=true` (the 1upHealth seam — gated OFF today)

Tracked in `api-wrapper/API.md` → "Pre-flip security gates":

- [ ] **HIGH-4** — wrapper error paths log/return correlation id + status only, never the
      upstream FHIR body (today they embed up to 500 chars of PHI-bearing body).
- [ ] **MEDIUM-7** — `app_user_id` derived server-side from the case owner (D2 identity
      work) + per-user authz at the wrapper. Never from tool args.

## Decided elsewhere (do not silently close)

- **MEDIUM-13** — account "deletion" retains case-file PHI under the stated retention
  posture. Counsel decision in the D2 / access-request-fulfillment track (noted in
  `runtime/app/routes/access_request.py`); consider crypto-shredding blobs on deletion.
- **MEDIUM-12** — chat cost/message caps are check-then-write (TOCTOU): the counters are
  aggregates over `messages`, so there is no per-user row to lock without a schema change.
  Deferred per the review's don't-over-build rule; bounded today (token-capped per turn,
  overshoot ≤ a few concurrent turns). Revisit with the Phase-4 Redis limiter work.
- **Per-replica in-memory rate limiting** — all sliding windows (magic-link, access-request,
  global) are per-replica until the Phase-4 Redis limiter; with >1 replica the effective
  limit is N× the configured one. Acceptable for V1-Lite; listed so nobody is surprised.
