import type {
  AccumulatorSnapshot,
  ClaimRecord,
  CoveragePlan,
  EncounterRecord,
} from "./domain.js";
import type { SourceResult, Vendor } from "./envelope.js";

/**
 * The four stable interfaces the wrapper exposes. Each may have multiple
 * adapters (e.g. AccumulatorSource is served by both a 1up-EOB-derived adapter
 * and a Stedi eligibility adapter). A resolver layer fans out to the registered
 * adapters and reconciles their SourceResults.
 *
 * Every method takes `appUserId` (Tyndale's own user id) and returns an ARRAY
 * of SourceResults: a patient may have multiple coverages, many claims, several
 * accumulator readings, etc. Disagreement between readings is preserved, not
 * flattened — reconciliation is a higher-layer concern.
 */

export interface ClaimsQuery {
  /** Only claims with service date on/after this ISO date. */
  since?: string;
}

export interface Source {
  readonly vendor: Vendor;
}

export interface CoverageSource extends Source {
  getCoverages(appUserId: string): Promise<SourceResult<CoveragePlan>[]>;
}

export interface ClaimsSource extends Source {
  getClaims(
    appUserId: string,
    query?: ClaimsQuery,
  ): Promise<SourceResult<ClaimRecord>[]>;
}

export interface AccumulatorSource extends Source {
  getAccumulators(
    appUserId: string,
  ): Promise<SourceResult<AccumulatorSnapshot>[]>;
}

export interface ClinicalEncounterSource extends Source {
  getEncounters(appUserId: string): Promise<SourceResult<EncounterRecord>[]>;
}
