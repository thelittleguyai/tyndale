import type {
  AccumulatorSnapshot,
  AccumulatorValue,
  ClaimLine,
  ClaimRecord,
  CoveragePlan,
  Money,
} from "../../core/domain.js";
import {
  codeOf,
  displayOf,
  hasCode,
  type Coverage,
  type EobAdjudication,
  type EobItem,
  type ExplanationOfBenefit,
  type FhirMoney,
} from "./fhir.js";

const DEFAULT_CURRENCY = "USD";

/** The distinct patient-responsibility buckets that ADD UP (do not overlap). */
const PATIENT_COMPONENTS = [
  "deductible",
  "copay",
  "coinsurance",
  "noncovered",
] as const;

function toMoney(m?: FhirMoney): Money | undefined {
  if (m?.value == null) return undefined;
  return { amount: m.value, currency: m.currency ?? DEFAULT_CURRENCY };
}

/** Amount of the single adjudication with exactly this category code. */
function amountForCode(
  adjs: EobAdjudication[] | undefined,
  code: string,
): Money | undefined {
  const hit = (adjs ?? []).find((a) => hasCode(a.category, code));
  return toMoney(hit?.amount);
}

/** First adjudication whose category code is in `codes` (for single-value fields). */
function firstAmount(
  adjs: EobAdjudication[] | undefined,
  codes: readonly string[],
): Money | undefined {
  for (const code of codes) {
    const m = amountForCode(adjs, code);
    if (m) return m;
  }
  return undefined;
}

/**
 * Patient responsibility = sum of the distinct cost-sharing buckets. Falls back
 * to a payer-stated "patientpay" total only when no components are present, so
 * we never double-count.
 */
function patientResponsibilityOf(
  adjs: EobAdjudication[] | undefined,
): Money | undefined {
  let total = 0;
  let currency = DEFAULT_CURRENCY;
  let found = false;
  for (const code of PATIENT_COMPONENTS) {
    const m = amountForCode(adjs, code);
    if (m) {
      total += m.amount;
      currency = m.currency;
      found = true;
    }
  }
  if (found) return { amount: total, currency };
  return amountForCode(adjs, "patientpay");
}

/** Sum a per-item derivation across many items (skips items that yield nothing). */
function sumOverItems(
  items: EobItem[],
  derive: (adjs: EobAdjudication[] | undefined) => Money | undefined,
): Money | undefined {
  let total = 0;
  let currency = DEFAULT_CURRENCY;
  let found = false;
  for (const item of items) {
    const m = derive(item.adjudication);
    if (m) {
      total += m.amount;
      currency = m.currency;
      found = true;
    }
  }
  return found ? { amount: total, currency } : undefined;
}

function normalizeLine(item: EobItem): ClaimLine {
  const line: ClaimLine = {};
  const cpt = codeOf(item.productOrService);
  if (cpt) line.cptCode = cpt;
  const desc = displayOf(item.productOrService);
  if (desc) line.description = desc;
  const billed = firstAmount(item.adjudication, ["submitted", "eligible"]);
  if (billed) line.billed = billed;
  const allowed = firstAmount(item.adjudication, ["eligible", "benefit"]);
  if (allowed) line.allowed = allowed;
  const paid = firstAmount(item.adjudication, ["benefit", "paidtoprovider"]);
  if (paid) line.insurerPaid = paid;
  const patient = patientResponsibilityOf(item.adjudication);
  if (patient) line.patientResponsibility = patient;
  return line;
}

export function normalizeEob(eob: ExplanationOfBenefit): ClaimRecord {
  const items = eob.item ?? [];
  const record: ClaimRecord = {
    claimId: eob.id ?? "unknown",
    lines: items.map(normalizeLine),
  };

  const start = eob.billablePeriod?.start;
  if (start) record.serviceStart = start;
  const end = eob.billablePeriod?.end;
  if (end) record.serviceEnd = end;
  const provider = eob.provider?.display;
  if (provider) record.provider = provider;
  if (eob.status) record.adjudicationStatus = eob.status;

  // Prefer claim-level totals; fall back to summing the line items.
  const billed =
    firstAmount(eob.total, ["submitted", "eligible"]) ??
    sumOverItems(items, (a) => firstAmount(a, ["submitted", "eligible"]));
  if (billed) record.billed = billed;
  const allowed =
    firstAmount(eob.total, ["eligible", "benefit"]) ??
    sumOverItems(items, (a) => firstAmount(a, ["eligible", "benefit"]));
  if (allowed) record.allowed = allowed;
  const insurerPaid =
    firstAmount(eob.total, ["benefit", "paidtoprovider"]) ??
    sumOverItems(items, (a) => firstAmount(a, ["benefit", "paidtoprovider"]));
  if (insurerPaid) record.insurerPaid = insurerPaid;
  const patient =
    patientResponsibilityOf(eob.total) ??
    sumOverItems(items, patientResponsibilityOf);
  if (patient) record.patientResponsibility = patient;

  return record;
}

export function normalizeCoverage(cov: Coverage): CoveragePlan {
  const plan: CoveragePlan = {};
  const payer = cov.payor?.[0]?.display;
  if (payer) plan.payerName = payer;
  if (cov.subscriberId) plan.memberId = cov.subscriberId;
  const planType = displayOf(cov.type);
  if (planType) plan.planType = planType;
  if (cov.status) plan.status = cov.status;
  if (cov.id) plan.planId = cov.id;
  const start = cov.period?.start;
  if (start) plan.coverageStart = start;
  const end = cov.period?.end;
  if (end) plan.coverageEnd = end;
  const group = cov.class?.find((c) => hasCode(c.type, "group"))?.value;
  if (group) plan.groupNumber = group;
  return plan;
}

/**
 * Reconstruct YTD accumulators by summing the patient-responsibility side of a
 * year of EOBs. This is the "computed-from-eob" reading: it tells us how much
 * has been *applied* to deductible/OOP, but NOT the plan's limits (those come
 * from benefits/eligibility). Limits are left undefined here on purpose.
 */
export function accumulatorsFromEobs(
  eobs: ExplanationOfBenefit[],
): AccumulatorSnapshot {
  const items = eobs.flatMap((e) => e.item ?? []);
  const deductibleMet = sumOverItems(items, (a) =>
    amountForCode(a, "deductible"),
  );
  const oopMet = sumOverItems(items, patientResponsibilityOf);

  const snapshot: AccumulatorSnapshot = {};
  if (deductibleMet) {
    const v: AccumulatorValue = { met: deductibleMet };
    snapshot.individualDeductible = v;
  }
  if (oopMet) {
    const v: AccumulatorValue = { met: oopMet };
    snapshot.individualOopMax = v;
  }
  return snapshot;
}
