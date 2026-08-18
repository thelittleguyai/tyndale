import assert from "node:assert/strict";
import { after, test } from "node:test";
import type http from "node:http";
import type { AddressInfo } from "node:net";

import { MissingTokensError, OneUpApiError } from "./oneup/errors.js";
import { createWrapperServer, type WrapperSources } from "./serverCore.js";

/**
 * The HTTP contract, exercised over real sockets on ephemeral ports. Every status the
 * server can produce is pinned: the unauthenticated health truth, timing-safe auth, the
 * method/path/param gates, the 503 gate envelope in both variants, and the error mapping —
 * including the property that an UNKNOWN error leaks nothing.
 */

const TOKEN = "test-bearer-token";

function fakeSources(overrides: Partial<WrapperSources> = {}): WrapperSources {
  const ok = { ok: true };
  return {
    coverage: { getCoverages: async () => ok },
    claims: { getClaims: async () => ok },
    accumulators: { getAccumulators: async () => ok },
    resolver: { getFinancialPicture: async () => ok },
    ...overrides,
  };
}

const servers: http.Server[] = [];

async function spin(opts?: {
  enabled?: boolean;
  sources?: WrapperSources | null;
}): Promise<string> {
  const server = createWrapperServer({
    authToken: TOKEN,
    enabled: opts?.enabled ?? true,
    sources: opts?.sources === undefined ? fakeSources() : opts.sources,
  });
  servers.push(server);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return `http://127.0.0.1:${port}`;
}

after(() => {
  for (const s of servers) s.close();
});

function get(base: string, path: string, token?: string): Promise<Response> {
  return fetch(`${base}${path}`, {
    headers: token === undefined ? {} : { authorization: token },
  });
}

const BEARER = `Bearer ${TOKEN}`;

// ── /health ──────────────────────────────────────────────────────────────────────────────
test("health is unauthenticated and reports both gate booleans truthfully", async () => {
  const base = await spin({ enabled: false, sources: null });
  const res = await get(base, "/health");
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "ok", enabled: false, configured: false });

  const on = await spin({ enabled: true });
  const body = await (await get(on, "/health")).json();
  assert.deepEqual(body, { status: "ok", enabled: true, configured: true });
});

// ── auth ─────────────────────────────────────────────────────────────────────────────────
test("timing-safe auth: missing, wrong, and prefix-mangled bearers are all 401", async () => {
  const base = await spin();
  for (const bad of [
    undefined, // no header at all
    "Bearer wrong-token-here", // wrong secret
    `bearer ${TOKEN}`, // mangled prefix (case matters — exact match only)
    `Bearer  ${TOKEN}`, // double space
    TOKEN, // bare token without the scheme
    `Bearer ${TOKEN}x`, // right prefix, near-miss secret
  ]) {
    const res = await get(base, "/v1/coverages?app_user_id=u1", bad);
    assert.equal(res.status, 401, `expected 401 for ${JSON.stringify(bad)}`);
    assert.deepEqual(await res.json(), { error: "unauthorized" });
  }
});

// ── method/path/param gates ──────────────────────────────────────────────────────────────
test("non-GET is 405 before auth is even considered", async () => {
  const base = await spin();
  const res = await fetch(`${base}/v1/claims?app_user_id=u1`, { method: "POST" });
  assert.equal(res.status, 405);
  assert.deepEqual(await res.json(), { error: "method_not_allowed" });
});

test("unknown paths are 404 for an authorized caller", async () => {
  const base = await spin();
  const res = await get(base, "/v1/nope?app_user_id=u1", BEARER);
  assert.equal(res.status, 404);
  assert.deepEqual(await res.json(), { error: "not_found" });
});

test("a data route without app_user_id is 400", async () => {
  const base = await spin();
  const res = await get(base, "/v1/claims", BEARER);
  assert.equal(res.status, 400);
  assert.deepEqual(await res.json(), { error: "missing_app_user_id" });
});

// ── the 503 gate envelope, both variants ─────────────────────────────────────────────────
test("gated OFF (enabled:false, credentials present) → 503 envelope says which", async () => {
  const base = await spin({ enabled: false });
  const res = await get(base, "/v1/coverages?app_user_id=u1", BEARER);
  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), {
    error: "coverage_connection_disabled",
    enabled: false,
    configured: true,
  });
});

test("unconfigured (enabled:true, no credentials) → 503 envelope says which", async () => {
  const base = await spin({ enabled: true, sources: null });
  const res = await get(base, "/v1/claims?app_user_id=u1", BEARER);
  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), {
    error: "coverage_connection_disabled",
    enabled: true,
    configured: false,
  });
});

// ── error mapping ────────────────────────────────────────────────────────────────────────
test("MissingTokensError maps to 424 missing_tokens", async () => {
  const base = await spin({
    sources: fakeSources({
      claims: {
        getClaims: async () => {
          throw new MissingTokensError("u1", "payer");
        },
      },
    }),
  });
  const res = await get(base, "/v1/claims?app_user_id=u1", BEARER);
  assert.equal(res.status, 424);
  const body = (await res.json()) as { error: string; message: string };
  assert.equal(body.error, "missing_tokens");
  assert.match(body.message, /payer OAuth/);
});

test("OneUpApiError maps to 502 with upstreamStatus", async () => {
  const base = await spin({
    sources: fakeSources({
      coverage: {
        getCoverages: async () => {
          throw new OneUpApiError(429, "https://api.1up.health/x", "rate limited");
        },
      },
    }),
  });
  const res = await get(base, "/v1/coverages?app_user_id=u1", BEARER);
  assert.equal(res.status, 502);
  const body = (await res.json()) as { error: string; upstreamStatus: number };
  assert.equal(body.error, "upstream_error");
  assert.equal(body.upstreamStatus, 429);
});

test("an unknown error is 500 internal_error and leaks NOTHING", async () => {
  const secret = "connection string with a password: hunter2";
  const base = await spin({
    sources: fakeSources({
      resolver: {
        getFinancialPicture: async () => {
          throw new Error(secret);
        },
      },
    }),
  });
  const res = await get(base, "/v1/financial-picture?app_user_id=u1", BEARER);
  assert.equal(res.status, 500);
  const raw = await res.text();
  assert.deepEqual(JSON.parse(raw), { error: "internal_error" });
  assert.ok(!raw.includes("hunter2"), "the error detail reached the response body");
});

test("routes forward the query: since becomes a ClaimsQuery", async () => {
  let seen: unknown = null;
  const base = await spin({
    sources: fakeSources({
      claims: {
        getClaims: async (_id, q) => {
          seen = q;
          return { ok: true };
        },
      },
    }),
  });
  await get(base, "/v1/claims?app_user_id=u1&since=2026-01-01", BEARER);
  assert.deepEqual(seen, { since: "2026-01-01" });
});
