# 1upHealth Wrapper Service — API Documentation

**Service:** `api-wrapper` (Jonas) · internal Container App `tyndale-dev-wrapper` · **Status:** deployed, gated OFF (`ENABLE_COVERAGE_CONNECTION=false`)
**Postman collection:** `api-wrapper/postman_collection.json` (import into Postman; set the three variables).

## What it is

A thin HTTP host over the wrapper's data-access library. It owns no business logic: it authenticates the caller, parses the query, and forwards to the vendor-neutral resolver/adapters (DL-68 interfaces). The Python runtime is its only intended caller.

## How to reach it

The deployed instance is **internal-ingress only — you cannot call it from your laptop.** For hands-on testing, run it locally:

```bash
cd api-wrapper
npm install         # zero runtime deps beyond node:20 stdlib; installs dev tooling
export PORT=8088
export WRAPPER_AUTH_TOKEN=dev-local-token          # anything; must match your requests
export ENABLE_COVERAGE_CONNECTION=true             # data routes 503 without this
# Optional — without these the service boots but data routes return 503:
export ONEUP_CLIENT_ID=...                         # 1up sandbox credentials
export ONEUP_CLIENT_SECRET=...
export ONEUP_ENVIRONMENT=sandbox
npm run start                                      # → wrapper-service listening on :8088
```

The deployed instance (for reference): `COVERAGE_WRAPPER_URL` env on the runtime points at the wrapper's internal FQDN (`:80` ingress → container `:8088`); the shared bearer is Key Vault secret `WRAPPER-AUTH-TOKEN` (`terraform output` can print it).

## Authentication

Every data route requires:
```
Authorization: Bearer <WRAPPER_AUTH_TOKEN>
```
Comparison is timing-safe. Missing/wrong token → `401 {"error":"unauthorized"}`. `/health` is deliberately unauthenticated (platform probes).

## Common behavior

- **GET only** — anything else: `405 {"error":"method_not_allowed"}`.
- **`app_user_id` is required on every data route** (query param). Today this is a passthrough id (the case_file_id placeholder); the real identity mapping is D2 work. Missing → `400 {"error":"missing_app_user_id"}`.
- **Gate honored server-side:** if `ENABLE_COVERAGE_CONNECTION` ≠ `true` **or** 1up credentials are absent, all data routes return `503 {"error":"coverage_connection_disabled","enabled":…,"configured":…}` — the two booleans tell you which condition failed.

## Endpoints

### `GET /health` — unauthenticated
```json
{ "status": "ok", "enabled": false, "configured": false }
```
`enabled` = the gate flag · `configured` = 1up credentials present and adapters built.

### `GET /v1/coverages?app_user_id={id}`
Active/inactive coverage plans. Returns `SourceResult<CoveragePlan>[]`:
```json
[
  {
    "value": {
      "payerName": "Blue Shield",
      "memberId": "XEG123456789",
      "groupNumber": "GRP-4417",
      "planId": "…",
      "planType": "PPO",
      "status": "active",
      "coverageStart": "2026-01-01",
      "coverageEnd": null
    },
    "provenance": { "vendor": "1upHealth", "method": "fhir-read", "sourceRefs": ["Coverage/…"], "retrievedAt": "2026-08-13T17:20:11Z" },
    "freshness": { "asOf": "2026-08-13T17:20:11Z", "ageDays": 0 },
    "confidence": { "level": "high", "reasons": [] }
  }
]
```

### `GET /v1/claims?app_user_id={id}&since={ISO-date}`
Adjudicated claims. `since` (optional) = only claims with service date on/after that ISO date. Returns `SourceResult<ClaimRecord>[]`; each `ClaimRecord`:
```json
{
  "claimId": "…",
  "serviceStart": "2026-04-02", "serviceEnd": "2026-04-02",
  "provider": "Maple Grove Family Medicine",
  "billed":   { "amount": 374.00, "currency": "USD" },
  "allowed":  { "amount": 254.50, "currency": "USD" },
  "insurerPaid": { "amount": 226.10, "currency": "USD" },
  "patientResponsibility": { "amount": 28.40, "currency": "USD" },
  "adjudicationStatus": "complete",
  "lines": [ { "cptCode": "99214", "description": "…", "billed": {…}, "allowed": {…}, "insurerPaid": {…}, "patientResponsibility": {…} } ]
}
```
All money is **dollars + ISO currency** (never cents).

### `GET /v1/accumulators?app_user_id={id}`
Deductible/OOP positions. Returns `SourceResult<AccumulatorSnapshot>[]` — note `method` will typically be `"computed-from-eob"` (reconstructed by summing EOB adjudications) or `"eob-stated-ytd"`; disagreement between readings is **preserved, not flattened** — reconciliation belongs to the runtime's cross-validation layer:
```json
{
  "value": {
    "planYearStart": "2026-01-01", "planYearEnd": "2026-12-31",
    "individualDeductible": { "limit": {"amount":2000,"currency":"USD"}, "met": {"amount":1750,"currency":"USD"}, "remaining": {"amount":250,"currency":"USD"} },
    "familyDeductible": null,
    "individualOopMax": { "limit": {"amount":6500,"currency":"USD"}, "met": {"amount":3200,"currency":"USD"}, "remaining": {"amount":3300,"currency":"USD"} },
    "familyOopMax": null
  },
  "provenance": { "vendor": "1upHealth", "method": "computed-from-eob", "retrievedAt": "…" },
  "freshness": { "asOf": "2026-08-01", "ageDays": 12 },
  "confidence": { "level": "medium", "reasons": ["payer omitted costToBeneficiary"] }
}
```

### `GET /v1/financial-picture?app_user_id={id}&since={ISO-date}`
The combined fan-out (one call, all four families — used when the runtime wants everything):
```json
{
  "coverages":    [ SourceResult<CoveragePlan> … ],
  "claims":       [ SourceResult<ClaimRecord> … ],
  "accumulators": [ SourceResult<AccumulatorSnapshot> … ],
  "encounters":   [ SourceResult<EncounterRecord> … ]
}
```
Prefer the individual routes when you need one family — the resolver fan-out triggers redundant upstream FHIR reads otherwise.

## The SourceResult envelope (every value, every route)

| Field | Meaning |
|---|---|
| `value` | The domain object (above) |
| `provenance.vendor` | `"1upHealth"` today; open string (`flexpa`, `stedi`, `user-upload`…) |
| `provenance.method` | `fhir-read` · `computed-from-eob` · `eligibility-271` · `eob-stated-ytd` · `user-upload` |
| `provenance.sourceRefs` | FHIR references / document ids it derives from |
| `provenance.retrievedAt` | When fetched (ISO 8601) |
| `freshness.asOf` / `ageDays` | The point in time the data *represents*; whole-day age (never negative) |
| `confidence.level` | `high` \| `medium` \| `low` + human-readable `reasons` |

## Error reference

| Status | Body | Meaning / what to do |
|---|---|---|
| 400 | `{"error":"missing_app_user_id"}` | Add the query param |
| 401 | `{"error":"unauthorized"}` | Bearer missing/wrong |
| 404 | `{"error":"not_found"}` | Unknown path |
| 405 | `{"error":"method_not_allowed"}` | GET only |
| **424** | `{"error":"missing_tokens","message":…}` | **The user has no connected payer yet** — a caller dependency, not a fault. The runtime treats this as "connection not established." |
| 502 | `{"error":"upstream_error","upstreamStatus":…,"message":…}` | 1up/FHIR upstream failed. ⚠️ `message` may embed upstream body today — a known pre-flip PHI-hardening item; don't log these bodies. |
| 503 | `{"error":"coverage_connection_disabled","enabled":…,"configured":…}` | Gate off or creds absent — check the two booleans |
| 500 | `{"error":"internal_error"}` | Check service logs |

## Known pre-flip caveats (why the gate stays off)
In-memory token store (payer tokens die on restart/scale-to-zero → **424s after any restart** until re-connect); `app_user_id` passthrough pending the D2 identity mapping; 502 `message` PHI-hardening. All tracked; none block local/sandbox testing.

### Pre-flip security gates (2026-08-19 review — MUST close before `ENABLE_COVERAGE_CONNECTION=true`)
1. **HIGH-4 — upstream error bodies are PHI.** `src/oneup/errors.ts` embeds up to 500 chars of
   the upstream FHIR body into error messages, which the runtime then surfaces. Before the flip:
   log a correlation id + status only — never the body, in responses or logs.
2. **MEDIUM-7 — per-user authz at the wrapper.** Any bearer holder can request any
   `app_user_id` (the Python mapper is a passthrough placeholder) → cross-patient FHIR read if
   an id is ever mis-set. Before the flip: derive `app_user_id` server-side from the case owner
   (the D2 identity work), never from tool args, and enforce per-user authz here.
