import http from "node:http";
import { timingSafeEqual } from "node:crypto";

import { loadConfig } from "./config.js";
import { OneUpClient } from "./oneup/client.js";
import { OneUpApiError, MissingTokensError } from "./oneup/errors.js";
import { InMemoryTokenStore } from "./store/tokenStore.js";
import {
  OneUpClaimsSource,
  OneUpCoverageSource,
  OneUpEobAccumulatorSource,
} from "./adapters/oneup/oneUpSource.js";
import { TyndaleResolver } from "./core/resolver.js";
import type { ClaimsQuery } from "./core/interfaces.js";

/**
 * HTTP host for the data-access library.
 *
 * The wrapper's adapters/resolver are a library; this thin server exposes them
 * over HTTP so the Python runtime can register matching source adapters behind
 * the same four DL-68 interfaces. It deliberately owns no business logic — it
 * authenticates the caller, parses the query, and forwards to the resolver.
 *
 * Deployment: runs as an internal-only Container App (no public ingress),
 * reached by the runtime over the VNet. Every data route requires a bearer
 * token that matches WRAPPER_AUTH_TOKEN (a Key-Vault secret both this service
 * and the runtime hold) — same shape as the qdrant api-key trust.
 *
 * TOKEN PERSISTENCE (fast-follow, blocks flipping the gate on): the only
 * TokenStore today is in-memory, so connected-payer tokens do NOT survive a
 * restart and are NOT shared across replicas. The Container App is pinned to a
 * single replica for dev; a Postgres-backed TokenStore is required before
 * ENABLE_COVERAGE_CONNECTION is turned on for real reads.
 */

const PORT = Number(process.env.PORT ?? "8088");

// The runtime seam is gated on this same flag; we honor it here too so a
// misconfigured caller can't pull vendor data while the connection is disabled.
const ENABLED = process.env.ENABLE_COVERAGE_CONNECTION === "true";

const AUTH_TOKEN = process.env.WRAPPER_AUTH_TOKEN;
if (!AUTH_TOKEN) {
  // Fail fast: without the shared secret every request would be unauthorized,
  // so there is no useful mode to run in.
  console.error("FATAL: WRAPPER_AUTH_TOKEN is not set; refusing to start.");
  process.exit(1);
}

interface Sources {
  coverage: OneUpCoverageSource;
  claims: OneUpClaimsSource;
  accumulators: OneUpEobAccumulatorSource;
  resolver: TyndaleResolver;
}

/**
 * Build the adapters + resolver from env-supplied 1up credentials. Returns null
 * when the credentials are absent (e.g. a gated-off deploy before the secrets
 * land), so the service still boots and serves /health while data routes 503.
 */
function buildSources(): Sources | null {
  try {
    const config = loadConfig();
    const store = new InMemoryTokenStore();
    const client = new OneUpClient({ config, store });
    const coverage = new OneUpCoverageSource({ client });
    const claims = new OneUpClaimsSource({ client });
    const accumulators = new OneUpEobAccumulatorSource({ client });
    // The resolver fans out across all adapters for the combined picture; the
    // individual routes call their one adapter directly to avoid redundant
    // upstream FHIR reads.
    const resolver = new TyndaleResolver({
      coverage: [coverage],
      claims: [claims],
      accumulators: [accumulators],
    });
    return { coverage, claims, accumulators, resolver };
  } catch (err) {
    console.warn(
      `1up credentials not configured; data routes will return 503. (${
        err instanceof Error ? err.message : String(err)
      })`,
    );
    return null;
  }
}

const sources = buildSources();
const CONFIGURED = sources !== null;

function authorized(req: http.IncomingMessage): boolean {
  const header = req.headers["authorization"] ?? "";
  const expected = `Bearer ${AUTH_TOKEN}`;
  const a = Buffer.from(header);
  const b = Buffer.from(expected);
  // timingSafeEqual requires equal lengths; the length check is not itself
  // constant-time but only leaks whether the header length matched.
  return a.length === b.length && timingSafeEqual(a, b);
}

function sendJson(res: http.ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

/** Map wrapper/vendor errors onto meaningful HTTP status codes. */
function sendError(res: http.ServerResponse, err: unknown): void {
  if (err instanceof MissingTokensError) {
    // The user has no connected payer (or 1up token) yet — a dependency the
    // caller must satisfy, not a server fault.
    sendJson(res, 424, { error: "missing_tokens", message: err.message });
    return;
  }
  if (err instanceof OneUpApiError) {
    sendJson(res, 502, {
      error: "upstream_error",
      upstreamStatus: err.status,
      message: err.message,
    });
    return;
  }
  console.error("Unhandled error serving request:", err);
  sendJson(res, 500, { error: "internal_error" });
}

type Handler = (
  appUserId: string,
  query: ClaimsQuery | undefined,
) => Promise<unknown>;

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`);
  const path = url.pathname;

  // Health is unauthenticated so the platform probe and the runtime can check
  // liveness without holding the bearer.
  if (req.method === "GET" && path === "/health") {
    sendJson(res, 200, {
      status: "ok",
      enabled: ENABLED,
      configured: CONFIGURED,
    });
    return;
  }

  if (req.method !== "GET") {
    sendJson(res, 405, { error: "method_not_allowed" });
    return;
  }

  if (!authorized(req)) {
    sendJson(res, 401, { error: "unauthorized" });
    return;
  }

  if (!ENABLED || sources === null) {
    sendJson(res, 503, {
      error: "coverage_connection_disabled",
      enabled: ENABLED,
      configured: CONFIGURED,
    });
    return;
  }

  const appUserId = url.searchParams.get("app_user_id");
  if (!appUserId) {
    sendJson(res, 400, { error: "missing_app_user_id" });
    return;
  }

  const since = url.searchParams.get("since");
  const query: ClaimsQuery | undefined = since ? { since } : undefined;

  const routes: Record<string, Handler> = {
    "/v1/coverages": (id) => sources.coverage.getCoverages(id),
    "/v1/claims": (id, q) => sources.claims.getClaims(id, q),
    "/v1/accumulators": (id) => sources.accumulators.getAccumulators(id),
    "/v1/financial-picture": (id, q) => sources.resolver.getFinancialPicture(id, q),
  };

  const handler = routes[path];
  if (!handler) {
    sendJson(res, 404, { error: "not_found" });
    return;
  }

  handler(appUserId, query)
    .then((body) => sendJson(res, 200, body))
    .catch((err) => sendError(res, err));
});

server.listen(PORT, () => {
  console.log(
    `wrapper-service listening on :${PORT} (enabled=${ENABLED}, configured=${CONFIGURED})`,
  );
});
