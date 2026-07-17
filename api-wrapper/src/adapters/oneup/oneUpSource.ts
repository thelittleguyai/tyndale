import type {
  AccumulatorSnapshot,
  ClaimRecord,
  CoveragePlan,
} from "../../core/domain.js";
import {
  ageInDays,
  type Confidence,
  type SourceResult,
} from "../../core/envelope.js";
import type {
  AccumulatorSource,
  ClaimsQuery,
  ClaimsSource,
  CoverageSource,
} from "../../core/interfaces.js";
import type { OneUpClient } from "../../oneup/client.js";
import {
  bundleResources,
  type Coverage,
  type ExplanationOfBenefit,
  type FhirBundle,
} from "./fhir.js";
import {
  accumulatorsFromEobs,
  normalizeCoverage,
  normalizeEob,
} from "./normalize.js";

const VENDOR = "1upHealth" as const;

export interface OneUpSourceOptions {
  client: OneUpClient;
  /** Injectable for tests. Defaults to Date.now. */
  now?: () => number;
}

/**
 * Base holding the shared OneUpClient and envelope-construction helpers. The
 * three concrete adapters below each implement one interface, so a consumer can
 * register only the capabilities it wants.
 */
abstract class OneUpBase {
  readonly vendor = VENDOR;
  protected readonly client: OneUpClient;
  protected readonly now: () => number;

  constructor({ client, now }: OneUpSourceOptions) {
    this.client = client;
    this.now = now ?? Date.now;
  }

  protected nowIso(): string {
    return new Date(this.now()).toISOString();
  }

  protected envelope<T>(
    value: T,
    method: SourceResult<T>["provenance"]["method"],
    opts: {
      sourceRefs?: string[];
      asOf?: string;
      confidence: Confidence;
    },
  ): SourceResult<T> {
    const retrievedAt = this.nowIso();
    const asOf = opts.asOf ?? retrievedAt;
    const provenance: SourceResult<T>["provenance"] = {
      vendor: VENDOR,
      method,
      retrievedAt,
    };
    if (opts.sourceRefs) provenance.sourceRefs = opts.sourceRefs;
    return {
      value,
      provenance,
      freshness: { asOf, ageDays: ageInDays(asOf, retrievedAt) },
      confidence: opts.confidence,
    };
  }
}

export class OneUpClaimsSource extends OneUpBase implements ClaimsSource {
  async getClaims(
    appUserId: string,
    query?: ClaimsQuery,
  ): Promise<SourceResult<ClaimRecord>[]> {
    const path = query?.since
      ? `ExplanationOfBenefit?service-date=ge${encodeURIComponent(query.since)}`
      : "ExplanationOfBenefit";
    const bundle = await this.client.fhirGet<
      FhirBundle<ExplanationOfBenefit>
    >(appUserId, path);
    const eobs = bundleResources(bundle);

    return eobs.map((eob) => {
      const record = normalizeEob(eob);
      const asOf = record.serviceEnd ?? record.serviceStart;
      return this.envelope(record, "fhir-read", {
        sourceRefs: [`ExplanationOfBenefit/${eob.id ?? "unknown"}`],
        ...(asOf ? { asOf } : {}),
        confidence: {
          level: "high",
          reasons: ["direct EOB line-item adjudication"],
        },
      });
    });
  }
}

export class OneUpCoverageSource extends OneUpBase implements CoverageSource {
  async getCoverages(
    appUserId: string,
  ): Promise<SourceResult<CoveragePlan>[]> {
    const bundle = await this.client.fhirGet<FhirBundle<Coverage>>(
      appUserId,
      "Coverage",
    );
    const coverages = bundleResources(bundle);

    return coverages.map((cov) => {
      const plan = normalizeCoverage(cov);
      return this.envelope(plan, "fhir-read", {
        sourceRefs: [`Coverage/${cov.id ?? "unknown"}`],
        ...(plan.coverageStart ? { asOf: plan.coverageStart } : {}),
        confidence: {
          level: "high",
          reasons: ["direct Coverage resource read"],
        },
      });
    });
  }
}

/**
 * Accumulators reconstructed from a year of EOBs. This is the confirmed
 * fallback for cost-sharing because Coverage.costToBeneficiary is unreliable
 * across payers. It yields amounts *applied* (met) but not plan *limits*, so
 * confidence is capped at medium and reasons say why.
 */
export class OneUpEobAccumulatorSource
  extends OneUpBase
  implements AccumulatorSource
{
  async getAccumulators(
    appUserId: string,
  ): Promise<SourceResult<AccumulatorSnapshot>[]> {
    const bundle = await this.client.fhirGet<
      FhirBundle<ExplanationOfBenefit>
    >(appUserId, "ExplanationOfBenefit");
    const eobs = bundleResources(bundle);
    const snapshot = accumulatorsFromEobs(eobs);

    const result = this.envelope(snapshot, "computed-from-eob", {
      sourceRefs: eobs.map((e) => `ExplanationOfBenefit/${e.id ?? "unknown"}`),
      confidence: {
        level: "medium",
        reasons: [
          "reconstructed by summing EOB adjudications",
          "plan limits not derivable from EOBs alone",
        ],
      },
    });
    return [result];
  }
}
