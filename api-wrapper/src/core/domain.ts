/**
 * Vendor-neutral domain types. Adapters normalize each vendor's payload into
 * these at the boundary, so the rest of the system never sees FHIR/271/vendor
 * quirks. Money is always dollars + ISO currency to avoid unit ambiguity.
 */

export interface Money {
  amount: number; // in major units (dollars), not cents
  currency: string; // ISO 4217, e.g. "USD"
}

export interface CoveragePlan {
  payerName?: string;
  memberId?: string;
  groupNumber?: string;
  planId?: string;
  planType?: string; // "PPO", "HMO", ...
  status?: string; // "active", "cancelled", ...
  coverageStart?: string; // ISO date
  coverageEnd?: string; // ISO date
}

export interface ClaimLine {
  cptCode?: string;
  description?: string;
  billed?: Money;
  allowed?: Money;
  insurerPaid?: Money;
  patientResponsibility?: Money;
}

export interface ClaimRecord {
  claimId: string;
  serviceStart?: string; // ISO date
  serviceEnd?: string; // ISO date
  provider?: string;
  billed?: Money;
  allowed?: Money;
  insurerPaid?: Money;
  patientResponsibility?: Money;
  adjudicationStatus?: string;
  lines: ClaimLine[];
}

export interface AccumulatorValue {
  limit?: Money; // the cap (deductible/OOP max)
  met?: Money; // amount applied so far
  remaining?: Money; // limit - met, when derivable
}

export interface AccumulatorSnapshot {
  planYearStart?: string; // ISO date
  planYearEnd?: string; // ISO date
  individualDeductible?: AccumulatorValue;
  familyDeductible?: AccumulatorValue;
  individualOopMax?: AccumulatorValue;
  familyOopMax?: AccumulatorValue;
}

export interface EncounterRecord {
  encounterId: string;
  date?: string; // ISO date
  type?: string;
  provider?: string;
  /** Free-text clinical notes, when the source actually exposes them. */
  notes?: string;
}
