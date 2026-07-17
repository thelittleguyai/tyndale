import type {
  AccumulatorSnapshot,
  ClaimRecord,
  CoveragePlan,
  EncounterRecord,
} from "./domain.js";
import type { SourceResult } from "./envelope.js";
import type {
  AccumulatorSource,
  ClaimsQuery,
  ClaimsSource,
  ClinicalEncounterSource,
  CoverageSource,
} from "./interfaces.js";

/**
 * Registry of adapters keyed by interface. Multiple adapters per interface are
 * allowed and expected (e.g. a 1up-EOB accumulator source alongside a Stedi
 * eligibility one). Order matters only as a tie-break hint for consumers.
 */
export interface ResolverSources {
  coverage?: CoverageSource[];
  claims?: ClaimsSource[];
  accumulators?: AccumulatorSource[];
  encounters?: ClinicalEncounterSource[];
}

/** Everything the wrapper can currently say about one user, with provenance. */
export interface FinancialPicture {
  coverages: SourceResult<CoveragePlan>[];
  claims: SourceResult<ClaimRecord>[];
  accumulators: SourceResult<AccumulatorSnapshot>[];
  encounters: SourceResult<EncounterRecord>[];
}

async function fanOut<T>(
  getters: (() => Promise<SourceResult<T>[]>)[],
): Promise<SourceResult<T>[]> {
  const settled = await Promise.allSettled(getters.map((g) => g()));
  const out: SourceResult<T>[] = [];
  for (const r of settled) {
    // A single failing vendor must not sink the whole picture; skip it. The
    // absence of its provenance in the result is itself the signal.
    if (r.status === "fulfilled") out.push(...r.value);
  }
  return out;
}

/**
 * Fans a request out across every registered adapter and concatenates their
 * enveloped results. It deliberately does NOT flatten disagreements — when two
 * accumulator readings differ, both survive with their own provenance so the
 * analysis layer can treat the discrepancy as a finding.
 */
export class TyndaleResolver {
  constructor(private readonly sources: ResolverSources) {}

  async getFinancialPicture(
    appUserId: string,
    query?: ClaimsQuery,
  ): Promise<FinancialPicture> {
    const [coverages, claims, accumulators, encounters] = await Promise.all([
      fanOut((this.sources.coverage ?? []).map((s) => () => s.getCoverages(appUserId))),
      fanOut((this.sources.claims ?? []).map((s) => () => s.getClaims(appUserId, query))),
      fanOut((this.sources.accumulators ?? []).map((s) => () => s.getAccumulators(appUserId))),
      fanOut((this.sources.encounters ?? []).map((s) => () => s.getEncounters(appUserId))),
    ]);

    return { coverages, claims, accumulators, encounters };
  }
}
