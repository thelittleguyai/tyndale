/**
 * Just enough FHIR R4 shape to normalize what 1upHealth returns. These are
 * intentionally partial: payers omit fields liberally, so nearly everything is
 * optional and every access must be guarded.
 */

export interface FhirBundle<T> {
  resourceType: "Bundle";
  entry?: { resource?: T }[];
}

export interface FhirMoney {
  value?: number;
  currency?: string;
}

export interface FhirCoding {
  system?: string;
  code?: string;
  display?: string;
}

export interface FhirCodeableConcept {
  coding?: FhirCoding[];
  text?: string;
}

export interface FhirPeriod {
  start?: string;
  end?: string;
}

export interface FhirReference {
  reference?: string; // e.g. "Organization/abc"
  display?: string;
}

export interface Coverage {
  resourceType: "Coverage";
  id?: string;
  status?: string;
  type?: FhirCodeableConcept;
  subscriberId?: string;
  period?: FhirPeriod;
  payor?: FhirReference[];
  class?: { type?: FhirCodeableConcept; value?: string; name?: string }[];
}

export interface EobAdjudication {
  category?: FhirCodeableConcept;
  amount?: FhirMoney;
}

export interface EobItem {
  productOrService?: FhirCodeableConcept;
  servicedDate?: string;
  servicedPeriod?: FhirPeriod;
  adjudication?: EobAdjudication[];
}

export interface ExplanationOfBenefit {
  resourceType: "ExplanationOfBenefit";
  id?: string;
  status?: string;
  billablePeriod?: FhirPeriod;
  provider?: FhirReference;
  item?: EobItem[];
  total?: EobAdjudication[];
}

/**
 * Real payer resources carry several codings per concept (e.g. a CARIN code
 * plus an HL7 adjudication code plus a display-only entry). Never assume the
 * one we want is first — scan for the first coding that actually has a code.
 */
export function codeOf(cc?: FhirCodeableConcept): string | undefined {
  return cc?.coding?.find((c) => c.code)?.code ?? cc?.text;
}

export function displayOf(cc?: FhirCodeableConcept): string | undefined {
  return cc?.coding?.find((c) => c.display)?.display ?? cc?.text ?? codeOf(cc);
}

/** True if ANY coding (or the free text) matches `code`, case-insensitively. */
export function hasCode(cc: FhirCodeableConcept | undefined, code: string): boolean {
  const target = code.toLowerCase();
  if (cc?.text?.toLowerCase() === target) return true;
  return (cc?.coding ?? []).some((c) => c.code?.toLowerCase() === target);
}

export function bundleResources<T>(bundle: FhirBundle<T>): T[] {
  return (bundle.entry ?? [])
    .map((e) => e.resource)
    .filter((r): r is T => r != null);
}
