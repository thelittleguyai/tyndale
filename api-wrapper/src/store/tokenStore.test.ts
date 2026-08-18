import assert from "node:assert/strict";
import { test } from "node:test";

import { InMemoryTokenStore } from "./tokenStore.js";
import type { StoredUserTokens } from "../oneup/types.js";

/**
 * The token store's semantics — including, IN THE TEST NAMES, the restart-loss property
 * that gates flipping ENABLE_COVERAGE_CONNECTION on for real reads (a Postgres-backed
 * TokenStore is the pre-flip requirement; see server.ts's deployment note).
 */

function tokens(appUserId = "usr_1"): StoredUserTokens {
  return {
    appUserId,
    oneUpUserId: 7,
    payer: {
      accessToken: "at",
      refreshToken: "rt",
      tokenType: "Bearer",
      expiresAt: Date.now() + 3_600_000,
      systemId: 42,
      resourceUrl: "https://payer.example/fhir",
      authBaseUrl: "https://payer.example/auth",
    },
  };
}

test("save/get roundtrips a user's tokens by appUserId", async () => {
  const store = new InMemoryTokenStore();
  const row = tokens();
  await store.save(row);
  assert.deepEqual(await store.get("usr_1"), row);
});

test("an unknown user is undefined, never a throw or an empty object", async () => {
  const store = new InMemoryTokenStore();
  assert.equal(await store.get("nobody"), undefined);
});

test("save overwrites: the latest tokens win (refresh flow)", async () => {
  const store = new InMemoryTokenStore();
  await store.save(tokens());
  const refreshed = tokens();
  refreshed.payer!.accessToken = "at-2";
  await store.save(refreshed);
  assert.equal((await store.get("usr_1"))!.payer!.accessToken, "at-2");
});

test("RESTART LOSES EVERYTHING: a new store instance has no rows — the property that gates the coverage-connection flip (Postgres-backed store required first)", async () => {
  const first = new InMemoryTokenStore();
  await first.save(tokens());
  const afterRestart = new InMemoryTokenStore();
  assert.equal(await afterRestart.get("usr_1"), undefined);
});

test("expiresAt is data, not behavior: the store returns expired tokens untouched (refresh is the client's judgment)", async () => {
  const store = new InMemoryTokenStore();
  const expired = tokens();
  expired.payer!.expiresAt = Date.now() - 1_000;
  await store.save(expired);
  const got = await store.get("usr_1");
  assert.ok(got && got.payer!.expiresAt < Date.now(), "the store must not filter or mutate");
});
