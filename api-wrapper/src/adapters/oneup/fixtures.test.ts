import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { OneUpApiError } from "../../oneup/errors.js";
import type { Coverage, ExplanationOfBenefit } from "./fhir.js";
import { normalizeCoverage, normalizeEob } from "./normalize.js";

/**
 * Normalization from COMMITTED sandbox-shaped fixtures (src/__fixtures__/) — the contract
 * the Python runtime consumes: Money is always dollars+currency, dates are ISO, lines map
 * 1:1, and a FHIR field the payer omitted is ABSENT in the domain object, never invented.
 * Plus the codified pre-flip PHI-hardening item (a visible todo, not an absence).
 */

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "__fixtures__");

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(join(FIXTURES, name), "utf8")) as T;
}

type Bundle<T> = { entry: { resource: T }[] };

test("coverage fixture: full entry normalizes with ISO dates; minimal entry invents nothing", () => {
  const bundle = fixture<Bundle<Coverage>>("coverage_bundle.json");
  const [full, minimal] = bundle.entry.map((e) => normalizeCoverage(e.resource));

  // planType prefers the human display over the bare code when the payer sent one.
  assert.equal(full!.planType, "Preferred Provider Organization");
  assert.equal(full!.payerName, "Blue Shield of Testland");
  assert.equal(full!.memberId, "MBR-889912");
  assert.equal(full!.groupNumber, "GRP-4471");
  // planId is the FHIR resource id — the stable reference — not the class "plan" value.
  assert.equal(full!.planId, "cov-full");
  assert.equal(full!.coverageStart, "2026-01-01");
  assert.equal(full!.coverageEnd, "2026-12-31");

  // The minimal Coverage stated nothing beyond status — nothing may appear invented.
  assert.equal(minimal!.payerName, undefined);
  assert.equal(minimal!.memberId, undefined);
  assert.equal(minimal!.groupNumber, undefined);
  assert.equal(minimal!.coverageStart, undefined);
  assert.equal(minimal!.coverageEnd, undefined);
});

test("eob fixture: Money is dollars+currency, lines map, omitted fields stay absent", () => {
  const bundle = fixture<Bundle<ExplanationOfBenefit>>("eob_bundle.json");
  const claim = normalizeEob(bundle.entry[0]!.resource);

  assert.equal(claim.serviceStart, "2026-03-14");
  assert.equal(claim.provider, "General Hospital");
  assert.equal(claim.lines.length, 2);
  const [mri, visit] = claim.lines;

  assert.equal(mri!.cptCode, "73721");
  assert.equal(mri!.description, "MRI lower extremity");
  assert.deepEqual(mri!.billed, { amount: 1850, currency: "USD" });
  assert.deepEqual(mri!.allowed, { amount: 900, currency: "USD" });
  // Patient responsibility = the DISTINCT buckets summed (deductible 120 + coinsurance 60).
  assert.deepEqual(mri!.patientResponsibility, { amount: 180, currency: "USD" });

  // The second line's payer stated only a submitted amount with NO currency: the currency
  // defaults (USD is the domain guarantee), and every unstated figure is ABSENT.
  assert.deepEqual(visit!.billed, { amount: 185, currency: "USD" });
  assert.equal(visit!.allowed, undefined);
  // description falls back to the CODE when the payer omitted a display — a label always
  // exists, but it is the document's own token, never an invented phrase.
  assert.equal(visit!.description, "99213");
});

test(
  "PRE-FLIP HARDENING (visible, not absent): an upstream error body must not reach error.message",
  { todo: "OneUpApiError embeds body.slice(0,500) in its message — upstream FHIR error bodies can carry patient identifiers, which then land in logs. Harden before ENABLE_COVERAGE_CONNECTION flips on for real reads." },
  () => {
    const body = readFileSync(join(FIXTURES, "malformed_upstream_error.json"), "utf8");
    const err = new OneUpApiError(422, "https://payer.example/fhir/ExplanationOfBenefit", body);
    // The payload stays available on the .body field for structured handling; the MESSAGE
    // (what reaches logs) must not carry it.
    assert.ok(
      !err.message.includes("MARGARET"),
      "upstream body (with a patient name) leaked into error.message",
    );
  },
);
