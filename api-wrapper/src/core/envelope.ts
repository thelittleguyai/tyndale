/**
 * Every value returned by a source adapter is wrapped in a SourceResult so the
 * consumer always knows *where* it came from, *how fresh* it is, and *how much*
 * to trust it. This is the contract that makes vendors swappable: two adapters
 * for the same interface return the same envelope shape, and the resolver layer
 * reconciles across them.
 */

/** Which vendor produced this data. Open string so new vendors need no enum edit. */
export type Vendor =
  | "1upHealth"
  | "flexpa"
  | "stedi"
  | "pverify"
  | "user-upload"
  | (string & {});

/** How the value was obtained — matters for trust and for reconciliation. */
export type DerivationMethod =
  | "fhir-read" // direct FHIR resource read (e.g. Coverage)
  | "computed-from-eob" // reconstructed by summing EOB adjudications
  | "eligibility-271" // live 270/271 real-time eligibility
  | "eob-stated-ytd" // a YTD figure the EOB itself stated
  | "user-upload"; // parsed from a document the patient uploaded

export interface Provenance {
  vendor: Vendor;
  method: DerivationMethod;
  /** FHIR reference(s) or document id(s) this was derived from, if any. */
  sourceRefs?: string[];
  /** When we fetched/derived it (ISO 8601). */
  retrievedAt: string;
}

export interface Freshness {
  /** The point in time the data actually represents (ISO 8601). */
  asOf: string;
  /** Whole days between `asOf` and `retrievedAt`; undefined if unknown. */
  ageDays?: number;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export interface Confidence {
  level: ConfidenceLevel;
  /** Human-readable reasons, e.g. "payer omitted costToBeneficiary". */
  reasons: string[];
}

export interface SourceResult<T> {
  value: T;
  provenance: Provenance;
  freshness: Freshness;
  confidence: Confidence;
}

/** Compute whole-day age, guarding against clock skew (never negative). */
export function ageInDays(asOf: string, retrievedAt: string): number {
  const from = Date.parse(asOf);
  const to = Date.parse(retrievedAt);
  if (Number.isNaN(from) || Number.isNaN(to)) return 0;
  return Math.max(0, Math.floor((to - from) / 86_400_000));
}
