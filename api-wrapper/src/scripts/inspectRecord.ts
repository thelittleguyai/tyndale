import { readFileSync } from "node:fs";
import {
  accumulatorsFromEobs,
  normalizeCoverage,
  normalizeEob,
} from "../adapters/oneup/normalize.js";
import type { Coverage, ExplanationOfBenefit } from "../adapters/oneup/fhir.js";

/**
 * Offline inspector: pipe a real record's exported FHIR JSON through the same
 * normalization the 1up adapter uses, with NO OAuth or network. Use it to sanity
 * -check that a payer's actual adjudication codes and resource shapes survive
 * our mapping before wiring the live flow.
 *
 *   npm run inspect -- ./real-record.json
 *
 * Accepts a FHIR Bundle, an array of Bundles/resources, or a single resource.
 */

interface AnyResource {
  resourceType?: string;
}

function collectResources(input: unknown): AnyResource[] {
  if (Array.isArray(input)) return input.flatMap(collectResources);
  if (input && typeof input === "object") {
    const obj = input as { resourceType?: string; entry?: unknown[] };
    if (obj.resourceType === "Bundle") {
      return (obj.entry ?? []).flatMap((e) =>
        collectResources((e as { resource?: unknown }).resource),
      );
    }
    if (obj.resourceType) return [obj as AnyResource];
  }
  return [];
}

function main(): void {
  const path = process.argv[2];
  if (!path) {
    console.error("usage: npm run inspect -- <path-to-fhir.json>");
    process.exit(1);
  }

  const raw = JSON.parse(readFileSync(path, "utf8")) as unknown;
  const resources = collectResources(raw);

  const eobs = resources.filter(
    (r): r is ExplanationOfBenefit & AnyResource =>
      r.resourceType === "ExplanationOfBenefit",
  );
  const coverages = resources.filter(
    (r): r is Coverage & AnyResource => r.resourceType === "Coverage",
  );

  const counts = new Map<string, number>();
  for (const r of resources) {
    const key = r.resourceType ?? "unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const output = {
    resourceCounts: Object.fromEntries(counts),
    coverages: coverages.map(normalizeCoverage),
    claims: eobs.map(normalizeEob),
    accumulatorsFromEobs: accumulatorsFromEobs(eobs),
  };

  console.log(JSON.stringify(output, null, 2));

  if (eobs.length === 0 && coverages.length === 0) {
    console.error(
      "\nNo ExplanationOfBenefit or Coverage resources found — nothing to normalize.",
    );
  }
}

main();
