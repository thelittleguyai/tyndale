import assert from "node:assert/strict";
import { test } from "node:test";
import type { Coverage, ExplanationOfBenefit } from "./fhir.js";
import {
  accumulatorsFromEobs,
  normalizeCoverage,
  normalizeEob,
} from "./normalize.js";

function usd(value: number) {
  return { value, currency: "USD" };
}
function adj(code: string, value: number) {
  return { category: { coding: [{ code }] }, amount: usd(value) };
}

const eob1: ExplanationOfBenefit = {
  resourceType: "ExplanationOfBenefit",
  id: "eob-1",
  status: "active",
  billablePeriod: { start: "2026-02-01", end: "2026-02-01" },
  provider: { display: "General Hospital" },
  item: [
    {
      productOrService: { coding: [{ code: "99213", display: "Office visit" }] },
      adjudication: [
        adj("submitted", 450.5),
        adj("eligible", 300),
        adj("benefit", 240),
        adj("deductible", 60),
      ],
    },
  ],
  total: [
    adj("submitted", 450.5),
    adj("eligible", 300),
    adj("benefit", 240),
    adj("deductible", 60),
  ],
};

// Second EOB: patient owes copay + coinsurance on one line (must SUM to 40).
const eob2: ExplanationOfBenefit = {
  resourceType: "ExplanationOfBenefit",
  id: "eob-2",
  status: "active",
  billablePeriod: { start: "2026-03-10" },
  item: [
    {
      productOrService: { coding: [{ code: "80050" }] },
      adjudication: [adj("submitted", 200), adj("copay", 25), adj("coinsurance", 15)],
    },
  ],
};

test("normalizeEob maps identity, service dates, and money fields", () => {
  const r = normalizeEob(eob1);
  assert.equal(r.claimId, "eob-1");
  assert.equal(r.serviceStart, "2026-02-01");
  assert.equal(r.serviceEnd, "2026-02-01");
  assert.equal(r.provider, "General Hospital");
  assert.equal(r.adjudicationStatus, "active");
  assert.deepEqual(r.billed, { amount: 450.5, currency: "USD" });
  assert.deepEqual(r.allowed, { amount: 300, currency: "USD" });
  assert.deepEqual(r.insurerPaid, { amount: 240, currency: "USD" });
  assert.deepEqual(r.patientResponsibility, { amount: 60, currency: "USD" });
  assert.equal(r.lines.length, 1);
  assert.equal(r.lines[0]?.cptCode, "99213");
  assert.equal(r.lines[0]?.description, "Office visit");
});

test("patient responsibility sums distinct cost-sharing buckets", () => {
  const r = normalizeEob(eob2);
  // copay 25 + coinsurance 15 = 40, not just the first bucket.
  assert.deepEqual(r.patientResponsibility, { amount: 40, currency: "USD" });
  assert.deepEqual(r.lines[0]?.patientResponsibility, {
    amount: 40,
    currency: "USD",
  });
});

test("category matching scans all codings, not just the first", () => {
  // Real payers list a CARIN code first and the HL7 adjudication code second.
  const eob: ExplanationOfBenefit = {
    resourceType: "ExplanationOfBenefit",
    id: "eob-multi",
    item: [
      {
        productOrService: {
          coding: [
            { system: "irrelevant", display: "Lab panel" },
            { system: "cpt", code: "80050" },
          ],
        },
        adjudication: [
          {
            category: {
              coding: [
                { system: "https://bluebutton.cms.gov/…/adjudication", code: "line_coinsurance_amount" },
                { system: "http://terminology.hl7.org/CodeSystem/adjudication", code: "deductible" },
              ],
            },
            amount: usd(75),
          },
        ],
      },
    ],
  };
  const r = normalizeEob(eob);
  assert.equal(r.lines[0]?.cptCode, "80050"); // skipped the display-only coding
  assert.deepEqual(r.patientResponsibility, { amount: 75, currency: "USD" });
});

test("normalizeCoverage pulls payer, member, plan type, and group", () => {
  const cov: Coverage = {
    resourceType: "Coverage",
    id: "cov-1",
    status: "active",
    subscriberId: "12345-6789",
    type: { coding: [{ code: "PPO", display: "PPO" }] },
    period: { start: "2026-01-01", end: "2026-12-31" },
    payor: [{ display: "Blue Shield" }],
    class: [{ type: { coding: [{ code: "group" }] }, value: "G12345" }],
  };
  const plan = normalizeCoverage(cov);
  assert.equal(plan.payerName, "Blue Shield");
  assert.equal(plan.memberId, "12345-6789");
  assert.equal(plan.planType, "PPO");
  assert.equal(plan.groupNumber, "G12345");
  assert.equal(plan.status, "active");
  assert.equal(plan.coverageStart, "2026-01-01");
  assert.equal(plan.coverageEnd, "2026-12-31");
});

test("accumulatorsFromEobs sums met amounts across a year of EOBs", () => {
  const snap = accumulatorsFromEobs([eob1, eob2]);
  // Only eob1 has a deductible bucket (60).
  assert.deepEqual(snap.individualDeductible?.met, {
    amount: 60,
    currency: "USD",
  });
  // OOP applied = 60 (eob1) + 40 (eob2 copay+coinsurance) = 100.
  assert.deepEqual(snap.individualOopMax?.met, { amount: 100, currency: "USD" });
  // Limits are intentionally not derivable from EOBs.
  assert.equal(snap.individualDeductible?.limit, undefined);
});
