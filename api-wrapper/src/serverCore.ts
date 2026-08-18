import http from "node:http";
import { timingSafeEqual } from "node:crypto";

import { OneUpApiError, MissingTokensError } from "./oneup/errors.js";
import type { ClaimsQuery } from "./core/interfaces.js";

/**
 * The HTTP host's behavior, extracted verbatim from server.ts (2026-08-18) so the test
 * suite can spin real servers on ephemeral ports with injected sources. server.ts remains
 * the deploy entry (env parsing, fail-fast, buildSources, listen) — nothing about the
 * running service changed in the split.
 */

/** The four data routes — exported so the docs-drift test can compare this table against
 *  postman_collection.json and API.md (a new route without docs fails the suite). */
export const ROUTE_PATHS = [
  "/v1/coverages",
  "/v1/claims",
  "/v1/accumulators",
  "/v1/financial-picture",
] as const;

/** Structural view of the adapters the routes call — the real OneUp sources satisfy it,
 *  and tests can inject fakes without touching vendor code. */
export interface WrapperSources {
  coverage: { getCoverages(appUserId: string): Promise<unknown> };
  claims: { getClaims(appUserId: string, q?: ClaimsQuery): Promise<unknown> };
  accumulators: { getAccumulators(appUserId: string): Promise<unknown> };
  resolver: { getFinancialPicture(appUserId: string, q?: ClaimsQuery): Promise<unknown> };
}

export interface WrapperOptions {
  authToken: string;
  enabled: boolean;
  sources: WrapperSources | null;
}

function authorized(req: http.IncomingMessage, authToken: string): boolean {
  const header = req.headers["authorization"] ?? "";
  const expected = `Bearer ${authToken}`;
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

export function createWrapperServer(opts: WrapperOptions): http.Server {
  const { authToken, enabled, sources } = opts;
  const configured = sources !== null;

  return http.createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    const path = url.pathname;

    // Health is unauthenticated so the platform probe and the runtime can check
    // liveness without holding the bearer.
    if (req.method === "GET" && path === "/health") {
      sendJson(res, 200, {
        status: "ok",
        enabled,
        configured,
      });
      return;
    }

    if (req.method !== "GET") {
      sendJson(res, 405, { error: "method_not_allowed" });
      return;
    }

    if (!authorized(req, authToken)) {
      sendJson(res, 401, { error: "unauthorized" });
      return;
    }

    if (!enabled || sources === null) {
      sendJson(res, 503, {
        error: "coverage_connection_disabled",
        enabled,
        configured,
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
}
