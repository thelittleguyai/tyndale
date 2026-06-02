# Admin console (admin.tyndaleapp.net)

Operations surface for the Tyndale team. Dual-layer auth (CO-6A): Google-OAuth admin role +
Terraform IP allowlist. **DL-60:** non-admins get **404** from every `/v1/admin/*` route — the
console's existence is never revealed. Every admin action is audited (acting admin + target user
+ action + timestamp) via `audit_admin_action` (actor = admin email, `user_id` = target).

## Modules

### 1. User management (`/users`)
List / search / status-filter users; detail view with account info, case files, and admin
action history. Actions (audited; `jwt_version` bumped where a session should be revoked):

- **Block / Unblock** — block sets a reason + bumps `jwt_version` (force-logout); unblock clears it (no bump).
- **Reset onboarding** — sets the user's case files to `intake_status='not_started'` + bumps `jwt_version`.
- **Force logout** — bumps `jwt_version` (invalidates outstanding tokens).
- **Send magic link** — fresh sign-in token via SendGrid; DL-47 (no PHI, token only).
- **Soft-delete** — anonymizes email (`deleted-<8hex>@deleted.tyndaleapp.net`), preserves `user_id` + case files + audit trail (HIPAA retention).
- **Set role** — grant/revoke admin (`user_type`); self-demotion is blocked.

JWT versioning: session tokens carry a `ver` claim. A request whose `ver` is stale vs the user's
`jwt_version` → 401 `JWT_INVALIDATED`; blocked → 403 `USER_BLOCKED`; soft-deleted → 401
`USER_DELETED`. (Enforced in `enforce_user_access`.)

### 2. RAG / knowledge viewer (`/knowledge`)
Browse the 4 Qdrant collections; semantic search (admin-unfiltered, staging excluded by default);
chunk detail + ingestion provenance; promote a staging chunk to live.

> **Deviation (flagged):** Qdrant payloads have no `partition_status` today — DL-59 staging is
> Postgres-only (transparency_rates). A chunk without the field reads as `live`, and **promote
> SETS** `partition_status='live'` + `sample_review_status='reviewed_pass'`. Counts show
> `staging=0` until chunks are tagged. The machinery is ready for staging-in-Qdrant.

### 3. Bill upload + AI comparison (`/cases`)
Case browse with filters (status, verdict, `q`, date range); detail is a tabbed comparison
(Documents / Reasoning / Response / Findings) + a verdict panel + **Export JSON**.

**Verdict vocabulary (v2)** — the structured fine-tune labels that feed the future **CO-6B**
chat-driven correction:

| verdict | meaning |
|---|---|
| `correct` | the analysis was right |
| `missed_finding` | a real issue was missed (list them in `missed_findings`) |
| `hallucinated` | a fabricated/unsupported claim (list them in `hallucinated_claims`) |
| `partial` | partly right |
| `unable_to_verify` | couldn't confirm either way |

CO-6B overlays natural-language correction on this structured base; the `missed_findings` /
`hallucinated_claims` lists are the labels it consumes. (Legacy CO-6A verdicts
`partially_correct`/`wrong` remain valid in the DB via the superset CHECK — migration 0015.)

### 4. Audit log viewer (`/audit`)
Filter by **target user** (the HIPAA "every access of patient X" query — indexed `user_id`),
acting admin, action type, tool, and date range. Row → expand for the full JSON payload.
**Export** produces a HIPAA-compliant access report (the full filtered set as JSON).
`action_type` is post-filtered in Python (audit payloads are clear-text bytes, not
JSONB-queryable); `user_id`/actor/date/tool are SQL-filtered.

**Export format** — `GET /v1/admin/audit-log/export?user_id=<X>`:
```json
{"exported_at":"…","filters":{…},"count":N,
 "entries":[{"event_id","timestamp","event_type","actor","target_user_id",
             "case_file_id","action","tools_invoked","outcome","payload"}]}
```
`user_id` = the target/patient; `actor` = the acting admin's email; the acting admin's id is also
in each entry's `payload.acting_admin_id`.

### 5. System health + cron control (`/system`)
Status tiles (Runtime / DB / Qdrant / Anthropic), deploy info, recent errors. Cron list with a
manual **Trigger** — each manual run records a `cron_run_log` row
(`triggered_source='manual_admin'`) + audit, runs in the **background**, and updates the row on
completion (returns `{run_id, status:'running'}`). `/system/crons/[name]` shows the full run
history. A `noop` cron exists for pipeline smoke-tests.

### 6. Knowledge gap log (`/gaps`)
The subagents call `log_knowledge_gap` when they hit a data gap (`no_data` / `low_confidence` /
`self_reported`) — wired into the bill_detective, math_person, and lead_planner system prompts.
The dashboard shows open-gap counts by agent + type, the top query clusters, and the raw log.

**Marking gaps resolved when ingestion closes them** — after, e.g., CO-2B Aetna policies ingest,
mark all gap clusters matching "Aetna" resolved with
`resolved_by_source = "CO-2B Aetna policies"` (per-gap `POST /v1/admin/knowledge-gaps/{id}/resolve`).

## Schema (migrations)
- `0012` users — block / soft-delete / `jwt_version` (+ DL-66 default backfill)
- `0013` `knowledge_gap_log`
- `0014` `cron_run_log`
- `0015` admin verdict v2 (superset CHECK + `missed_findings` / `hallucinated_claims`)
