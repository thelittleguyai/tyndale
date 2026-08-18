import { loadConfig } from "./config.js";
import { OneUpClient } from "./oneup/client.js";
import { InMemoryTokenStore } from "./store/tokenStore.js";
import {
  OneUpClaimsSource,
  OneUpCoverageSource,
  OneUpEobAccumulatorSource,
} from "./adapters/oneup/oneUpSource.js";
import { TyndaleResolver } from "./core/resolver.js";
import { createWrapperServer, type WrapperSources } from "./serverCore.js";

/**
 * HTTP host for the data-access library — the deploy ENTRY. All request behavior lives in
 * serverCore.ts (extracted verbatim 2026-08-18 so the test suite can spin real servers on
 * ephemeral ports); this file owns exactly what a process entry owns: env parsing, the
 * fail-fast, adapter construction, and listen().
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

/**
 * Build the adapters + resolver from env-supplied 1up credentials. Returns null
 * when the credentials are absent (e.g. a gated-off deploy before the secrets
 * land), so the service still boots and serves /health while data routes 503.
 */
function buildSources(): WrapperSources | null {
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

const server = createWrapperServer({
  authToken: AUTH_TOKEN,
  enabled: ENABLED,
  sources,
});

server.listen(PORT, () => {
  console.log(
    `wrapper-service listening on :${PORT} (enabled=${ENABLED}, configured=${sources !== null})`,
  );
});
