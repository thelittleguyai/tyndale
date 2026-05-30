# Runtime Hardening (Phase 2K.2)

Fills the security gap opened by **DL-42** (the runtime moved from internal-only
to public at `api.tyndaleapp.net`). The original developer-spec D9 assumed no
public surface; this phase is the **minimum** application-layer hardening so
V1-Lite can take real user traffic in dev. Phase 4 (the security/HIPAA contact)
builds on top of it.

## What was hardened

| Area | Where | Behavior |
|---|---|---|
| Rate limiting (all routes) | `middleware/rate_limit.py` | per-IP baseline (100/min, 1000/hr); per-user when authenticated (200/min, 2000/hr); per-route hourly caps on expensive POSTs (upload/extract/finalize 20, confirmations 50). 429 + `Retry-After`. `/health` exempt. |
| Security headers | `middleware/security_headers.py` | HSTS, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `X-DNS-Prefetch-Control`; strict CSP on non-HTML responses. |
| Request size limits | `middleware/request_size.py` + `routes/upload.py` | 25 MB total multipart / 1 MB JSON (middleware, by Content-Length) + 20 MB per uploaded file (route). 413 on overflow. |
| Error responses | `middleware/error_handler.py` | prod: no traceback/exception detail — `correlation_id` + `request_id` only (look the traceback up in the structured log). dev: traceback retained (DL-29). |
| JWT validation | `auth/jwt.py` | explicit `algorithms=["HS256"]` (defeats alg-confusion), explicit audience + issuer, required-claim list, explicit `verify_*` options. |
| CORS | `middleware/cors.py` | explicit origin allow-list (never `*`), `allow_credentials=True`, explicit methods + headers; dev adds `localhost:3000`/`:8081`. |
| Session cookie | `config.py`, `routes/auth.py`, `auth/current_user.py` | writes `__Secure-tyndale_session` over HTTPS; **reads both** that and the legacy `tyndale_session` (30-day grace — no forced logout). |
| PHI log filter | `middleware/phi_log_filter.py` | coarse regex scrub (SSN, email, member-ID, MRN, $-paired-with-identifier) on the app log via a structlog processor. **Bridge before Presidio.** |
| Admin IP allowlist | `middleware/admin_ip_allowlist.py` | env CIDR allowlist on `/v1/admin/*` (no such routes yet — preventive). |
| Anti-enumeration | existing + tests | `/v1/auth/magic-link-request` always 200; `/v1/user/me` + `/v1/feedback` return a generic 401 that never reveals account existence. |

## Production deployment checklist

Env vars (all have safe defaults; override only to tune):

| Var | Default | Notes |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | tests set `false` |
| `RATE_LIMIT_PER_IP_PER_MINUTE` / `_PER_HOUR` | 100 / 1000 | |
| `RATE_LIMIT_PER_USER_PER_MINUTE` / `_PER_HOUR` | 200 / 2000 | |
| `RATE_LIMIT_UPLOAD_PER_HOUR` / `_EXTRACT_` / `_FINALIZE_` / `_CONFIRMATIONS_` | 20 / 20 / 20 / 50 | |
| `TRUST_FORWARDED_FOR_HOPS` | 1 | Container Apps LB hop count |
| `SECURITY_HEADERS_ENABLED` | `true` | |
| `MAX_REQUEST_BODY_BYTES` / `MAX_JSON_BODY_BYTES` / `MAX_UPLOAD_FILE_BYTES` | 25 MB / 1 MB / 20 MB | |
| `ADMIN_ALLOWED_IPS` | `""` (no restriction) | comma-separated CIDR when admin routes land |
| `SESSION_COOKIE_SECURE_PREFIX` | `true` | `__Secure-` prefix when `COOKIE_SECURE=true` |

- The `__Secure-` cookie cutover has a **30-day grace period** — existing `tyndale_session` cookies are still read. Cookie attrs to confirm in DevTools after deploy: name `__Secure-tyndale_session`, `Secure`, `HttpOnly`, `SameSite=Lax`, `Domain=.tyndaleapp.net`.
- Suggested monitoring alerts (App Insights / Log Analytics): spike in 429s (abuse or a misbehaving client), 413s (oversized uploads), 500s by `correlation_id`, and auth-failure rate.

## Deferred to Phase 4 (security/HIPAA contact — name TBD)

- **Redis-backed rate limiter** — today's limiter is in-memory **per-replica**; with >1 replica the limits are per-replica, not global. Fine for current V1-Lite traffic.
- **Microsoft Presidio** scrubbing + custom recognizers (replaces the coarse PHI log filter; see `docs/integration-contracts.md` §2.1 PreToolUse hook).
- **Encrypted audit log** (AES-GCM) + Key Vault key rotation.
- **Front Door / Application Gateway WAF** with path-based IP rules (Container Apps can only IP-restrict the whole environment, so the admin IP allowlist lives at the app layer for now).
- **mTLS** for runtime ↔ litellm if needed.
