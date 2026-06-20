/**
 * Provenance — the typed source-attribution object every data-interface return
 * carries (DL-69). Mirrors runtime/app/schemas/provenance.py one-for-one
 * (snake_case, like the rest of packages/shared).
 *
 * Supersedes the bare `extraction_source: "upload"` string the upload-extract
 * tools used to emit. It is a strict superset of what was persisted before, so
 * threading it through tool returns / the case file / findings is additive —
 * it never removes or renames an existing key.
 */

export type ProvenanceSourceKind = 'user_upload' | 'public_data' | 'computed' | 'vendor';

export interface Provenance {
  /**
   * Which adapter produced the value — e.g. "UserUploadedSBC", "UserUploadedEOB",
   * "PlanLibrary", "OneUpHealthCoverage", "EligibilityVendorBenefits".
   */
  adapter: string;
  source_kind: ProvenanceSourceKind;
  /**
   * ISO date/datetime the data is current as-of, or null. REQUIRED (non-null)
   * for AccumulatorSource — accumulator math is freshness-sensitive (DL-69).
   */
  as_of: string | null;
  /** 0.0–1.0 confidence in the value. */
  confidence: number;
  /** Human-readable assumptions the adapter made (e.g. OCR heuristics). */
  assumptions: string[];
}
