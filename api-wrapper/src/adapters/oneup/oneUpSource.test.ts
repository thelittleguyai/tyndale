import assert from "node:assert/strict";
import { test } from "node:test";
import type { OneUpConfig } from "../../config.js";
import { OneUpClient } from "../../oneup/client.js";
import { InMemoryTokenStore } from "../../store/tokenStore.js";
import {
  OneUpClaimsSource,
  OneUpCoverageSource,
  OneUpEobAccumulatorSource,
} from "./oneUpSource.js";

const FIXED = Date.parse("2026-07-07T00:00:00.000Z");
const now = () => FIXED;

const config: OneUpConfig = {
  environment: "sandbox",
  clientId: "cid",
  clientSecret: "secret",
  redirectUri: "https://app.tyndale.test/callback",
  scope: "user/*.read",
  baseUrls: {
    userManagement: "https://api.1up.health",
    auth: "https://auth.1up.health",
    systemSearch: "https://system-search.1up.health",
  },
};

const eobBundle = {
  resourceType: "Bundle",
  entry: [
    {
      resource: {
        resourceType: "ExplanationOfBenefit",
        id: "eob-1",
        status: "active",
        billablePeriod: { start: "2026-02-01", end: "2026-02-01" },
        provider: { display: "General Hospital" },
        item: [
          {
            productOrService: { coding: [{ code: "99213" }] },
            adjudication: [
              { category: { coding: [{ code: "submitted" }] }, amount: { value: 450.5, currency: "USD" } },
              { category: { coding: [{ code: "eligible" }] }, amount: { value: 300, currency: "USD" } },
              { category: { coding: [{ code: "benefit" }] }, amount: { value: 240, currency: "USD" } },
              { category: { coding: [{ code: "deductible" }] }, amount: { value: 60, currency: "USD" } },
            ],
          },
        ],
      },
    },
  ],
};

const coverageBundle = {
  resourceType: "Bundle",
  entry: [
    {
      resource: {
        resourceType: "Coverage",
        id: "cov-1",
        status: "active",
        subscriberId: "12345-6789",
        type: { coding: [{ code: "PPO", display: "PPO" }] },
        period: { start: "2026-01-01", end: "2026-12-31" },
        payor: [{ display: "Blue Shield" }],
      },
    },
  ],
};

/** Seed a user with a fresh payer token and a fetch that serves fixtures. */
function harness() {
  const store = new InMemoryTokenStore();
  const calls: string[] = [];
  const fetchImpl: typeof fetch = async (input) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push(url);
    const body = url.includes("Coverage") ? coverageBundle : eobBundle;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/fhir+json" },
    });
  };
  const client = new OneUpClient({ config, store, fetchImpl, now });
  const seed = store.save({
    appUserId: "usr_test",
    oneUpUserId: 1,
    payer: {
      accessToken: "payer-access",
      refreshToken: "payer-refresh",
      tokenType: "Bearer",
      expiresAt: FIXED + 3_600_000,
      systemId: 42,
      resourceUrl: "https://payer.example/fhir",
      authBaseUrl: "https://payer.example/auth",
    },
  });
  return { client, calls, seed };
}

test("OneUpClaimsSource: fetch -> normalize -> enveloped SourceResult", async () => {
  const { client, calls, seed } = harness();
  await seed;
  const src = new OneUpClaimsSource({ client, now });
  const results = await src.getClaims("usr_test");

  assert.equal(results.length, 1);
  const r = results[0]!;
  assert.equal(r.value.claimId, "eob-1");
  assert.deepEqual(r.value.patientResponsibility, { amount: 60, currency: "USD" });
  assert.deepEqual(r.value.insurerPaid, { amount: 240, currency: "USD" });

  assert.equal(r.provenance.vendor, "1upHealth");
  assert.equal(r.provenance.method, "fhir-read");
  assert.deepEqual(r.provenance.sourceRefs, ["ExplanationOfBenefit/eob-1"]);
  assert.equal(r.provenance.retrievedAt, "2026-07-07T00:00:00.000Z");
  assert.equal(r.freshness.asOf, "2026-02-01");
  assert.ok((r.freshness.ageDays ?? 0) > 150);
  assert.equal(r.confidence.level, "high");

  // Hit the payer's FHIR base, not 1up's platform host.
  assert.ok(calls[0]?.startsWith("https://payer.example/fhir/ExplanationOfBenefit"));
});

test("OneUpClaimsSource: since filter builds a service-date search param", async () => {
  const { client, calls, seed } = harness();
  await seed;
  const src = new OneUpClaimsSource({ client, now });
  await src.getClaims("usr_test", { since: "2026-01-01" });
  assert.ok(calls[0]?.includes("service-date=ge2026-01-01"));
});

test("OneUpCoverageSource normalizes a Coverage resource", async () => {
  const { client, seed } = harness();
  await seed;
  const src = new OneUpCoverageSource({ client, now });
  const results = await src.getCoverages("usr_test");
  assert.equal(results.length, 1);
  const plan = results[0]!.value;
  assert.equal(plan.payerName, "Blue Shield");
  assert.equal(plan.memberId, "12345-6789");
  assert.equal(plan.planType, "PPO");
  assert.equal(results[0]!.provenance.method, "fhir-read");
});

test("OneUpEobAccumulatorSource reconstructs met amounts at medium confidence", async () => {
  const { client, seed } = harness();
  await seed;
  const src = new OneUpEobAccumulatorSource({ client, now });
  const results = await src.getAccumulators("usr_test");
  assert.equal(results.length, 1);
  const snap = results[0]!.value;
  assert.deepEqual(snap.individualDeductible?.met, { amount: 60, currency: "USD" });
  assert.equal(snap.individualDeductible?.limit, undefined);
  assert.equal(results[0]!.provenance.method, "computed-from-eob");
  assert.equal(results[0]!.confidence.level, "medium");
});
