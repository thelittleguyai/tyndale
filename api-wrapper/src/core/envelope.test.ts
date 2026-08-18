import assert from "node:assert/strict";
import { test } from "node:test";

import { ageInDays } from "./envelope.js";

/**
 * The envelope's one computed value. Carriage of the full SourceResult shape
 * (provenance vendor/method/retrievedAt, freshness, confidence with reasons) is asserted
 * against real adapter output in oneUpSource.test.ts — here the guard rails of ageInDays.
 */

test("ageInDays: whole days between asOf and retrievedAt", () => {
  assert.equal(ageInDays("2026-02-01", "2026-07-07T00:00:00.000Z"), 156);
  assert.equal(ageInDays("2026-07-07T00:00:00.000Z", "2026-07-07T23:59:00.000Z"), 0);
});

test("ageInDays clock-skew guard: a retrievedAt BEFORE asOf is 0, never negative", () => {
  assert.equal(ageInDays("2026-07-08", "2026-07-07T00:00:00.000Z"), 0);
});

test("ageInDays: unparseable dates degrade to 0, never NaN", () => {
  assert.equal(ageInDays("not-a-date", "2026-07-07"), 0);
  assert.equal(ageInDays("2026-07-07", ""), 0);
});
