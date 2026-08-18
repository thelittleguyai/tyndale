import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { ROUTE_PATHS } from "./serverCore.js";

/**
 * Docs drift: the server's route table must appear in BOTH postman_collection.json and
 * API.md. A new route without docs fails here — the docs are part of the deliverable,
 * not an afterthought (they are also why those two files are committed).
 */

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function postmanPaths(): Set<string> {
  const collection = JSON.parse(
    readFileSync(join(ROOT, "postman_collection.json"), "utf8"),
  ) as { item: { request?: { url?: { path?: string[] } }; item?: unknown[] }[] };
  const paths = new Set<string>();
  const walk = (items: { request?: { url?: { path?: string[] } }; item?: unknown[] }[]) => {
    for (const item of items) {
      const segs = item.request?.url?.path;
      if (segs?.length) paths.add("/" + segs.join("/"));
      if (Array.isArray(item.item)) walk(item.item as typeof items);
    }
  };
  walk(collection.item);
  return paths;
}

test("every server route is in the postman collection (and /health too)", () => {
  const documented = postmanPaths();
  for (const route of [...ROUTE_PATHS, "/health"]) {
    assert.ok(documented.has(route), `route ${route} missing from postman_collection.json`);
  }
});

test("every server route is documented in API.md (and /health too)", () => {
  const md = readFileSync(join(ROOT, "API.md"), "utf8");
  for (const route of [...ROUTE_PATHS, "/health"]) {
    assert.ok(md.includes(route), `route ${route} missing from API.md`);
  }
});

test("the postman collection documents no route the server doesn't serve", () => {
  const served = new Set<string>([...ROUTE_PATHS, "/health"]);
  for (const path of postmanPaths()) {
    assert.ok(served.has(path), `postman documents ${path}, which the server does not serve`);
  }
});
