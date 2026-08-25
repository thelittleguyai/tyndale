/**
 * Humanized finding card for the audit-results screen.
 *
 * Leads with the recommendation ("What to do"), translates finding_type and
 * voice_tier into plain language, and tucks the raw facts behind a collapsed
 * "Details" disclosure instead of dumping snake_case keys.
 */

import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ChevronDown, ChevronRight } from 'lucide-react-native';

import type { FindingOut, ThumbsValue } from '../../lib/api-client';
import { displayEnum } from '../../lib/enum-display';
import { ThumbsRating } from '../thumbs-rating';

const TYPE_LABELS: Record<FindingOut['finding_type'], string> = {
  payer_side: 'Your insurer may have miscalculated',
  provider_side: 'The provider may have overbilled',
  encounter_mismatch: 'This may not match what happened',
};

const TIER_LABELS: Record<FindingOut['voice_tier'], string> = {
  A: 'Strong evidence',
  B: 'Good evidence',
  C: 'Worth asking about',
};

/** snake_case → "Sentence case". */
function prettifyKey(key: string): string {
  const words = key.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const MONEY_KEY = /(billed|computed|responsibilit|amount|cost|price|charge|owe|gap|rate|paid|fee|total|balance|saving)/i;

function formatFactValue(key: string, value: unknown): string {
  if (typeof value === 'number' && MONEY_KEY.test(key)) {
    return `$${value.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

/** Pull a sensible "what to do" string set out of the loosely-typed recommendation. */
function recommendationLines(rec: Record<string, unknown>): { main: string | null; support: string | null; rest: string[] } {
  // displayEnum guards against a raw snake_case action enum leaking to screen (prose passes through).
  const main = typeof rec.action === 'string' ? displayEnum(rec.action) : null;
  const support = typeof rec.reasoning === 'string' ? rec.reasoning : null;
  const rest: string[] = [];
  for (const [k, v] of Object.entries(rec)) {
    if (k === 'action' || k === 'reasoning' || v == null) continue;
    rest.push(`${prettifyKey(k)}: ${formatFactValue(k, v)}`);
  }
  // No recognizable action key — fall back to prettified values so we never
  // hide a recommendation just because its shape drifted.
  if (!main && rest.length === 0 && support) return { main: support, support: null, rest: [] };
  return { main, support, rest };
}

export function FindingCard({
  finding,
  caseFileId,
  existingRating,
}: {
  finding: FindingOut;
  caseFileId: string;
  existingRating: ThumbsValue | null;
}) {
  const [showDetails, setShowDetails] = useState(false);

  const lc = (finding.legal_claim ?? {}) as Record<string, unknown>;
  const rec = (finding.recommendation ?? null) as Record<string, unknown> | null;
  const recLines = rec ? recommendationLines(rec) : null;
  const facts = finding.facts ?? {};
  const factEntries = Object.entries(facts);

  // Rose is reserved for confirmed provider-side overcharges; everything else
  // (insurer math, encounter mismatches) reads as caution, not alarm.
  const isRose = finding.finding_type === 'provider_side';
  const borderClass = isRose ? 'border-danger' : 'border-warning';

  // Attribution (Brock 38 §3): the server-derived responsible_party decides the header —
  // a payer-adjudication rule's finding says "insurer" even if typed provider_side, and
  // 'either' gets the both-parties line (engineering copy, flagged for Brock's pass).
  const ATTRIBUTION_LABELS: Record<string, string> = {
    payer: TYPE_LABELS.payer_side,
    provider: TYPE_LABELS.provider_side,
    either: 'Worth checking with both your provider and insurer',
  };
  const typeLabel =
    (finding.responsible_party ? ATTRIBUTION_LABELS[finding.responsible_party] : undefined) ??
    TYPE_LABELS[finding.finding_type] ??
    'Something worth a closer look';
  const tierLabel = TIER_LABELS[finding.voice_tier] ?? 'Worth asking about';

  return (
    <View className={`mb-3 rounded-2xl border ${borderClass} bg-surface p-4`}>
      <View className="mb-2 flex-row items-start justify-between">
        <Text className="flex-1 pr-2 text-base font-semibold text-primary">{typeLabel}</Text>
        <View className="flex-row items-center gap-2 pt-0.5">
          <View className="rounded-md bg-inset px-2 py-0.5">
            <Text className="text-[10px] font-semibold text-secondary">{tierLabel}</Text>
          </View>
          <ThumbsRating
            target={{ type: 'finding', id: finding.finding_id }}
            caseFileId={caseFileId}
            existingRating={existingRating}
            size={15}
          />
        </View>
      </View>

      {recLines && (recLines.main || recLines.rest.length > 0) ? (
        <View className="mb-3 rounded-xl bg-accent-tint p-3">
          <Text className="mb-1 text-[10px] font-semibold text-accent">
            What to do
          </Text>
          {recLines.main ? (
            <Text className="text-body leading-6 text-primary">{recLines.main}</Text>
          ) : null}
          {recLines.support ? (
            <Text className="mt-1 text-xs leading-4 text-secondary">{recLines.support}</Text>
          ) : null}
          {recLines.rest.map((line) => (
            <Text key={line} className="mt-1 text-xs leading-4 text-secondary">
              {line}
            </Text>
          ))}
        </View>
      ) : null}

      {typeof lc.claim === 'string' ? (
        <Text className="mb-2 text-body leading-6 text-primary">
          {lc.claim}
          {typeof lc.marker === 'string' ? (
            <Text className="text-xs text-faint"> {lc.marker}</Text>
          ) : null}
        </Text>
      ) : null}

      {/* E4/H3 — THE GROUNDING LINE. Always one of two states, never nothing. B5 (Brock
          2026-08-18) decides the CHIP: a rule-based finding (law / regulation / plan
          provision) renders its source as a citation chip in the citation blue — chip
          REQUIRED, and the server already swapped an uncited one to the no-source line —
          while a fact finding (arithmetic, direct observation) renders its source as plain
          text with NO chip: chips on arithmetic teach users to ignore chips. */}
      {finding.has_source && finding.tier === 'rule_based' ? (
        <View className="mb-2 self-start rounded-chip bg-citation-tint px-2.5 py-1" testID="citation-chip">
          <Text className="text-micro text-citation-on-tint">{finding.source_line}</Text>
        </View>
      ) : finding.has_source ? (
        <Text className="mb-2 text-micro leading-4 text-secondary" testID="fact-source-line">
          {finding.source_line}
        </Text>
      ) : (
        <Text className="mb-2 text-micro italic leading-4 text-faint" testID="no-source-line">
          {finding.source_line}
        </Text>
      )}

      {factEntries.length > 0 ? (
        <View className="mt-1">
          <Pressable
            onPress={() => setShowDetails((v) => !v)}
            className="flex-row items-center gap-1 py-1"
            accessibilityRole="button"
          >
            {showDetails ? (
              <ChevronDown size={13} color="var(--c-text-faint)" />
            ) : (
              <ChevronRight size={13} color="var(--c-text-faint)" />
            )}
            <Text className="text-xs font-semibold text-faint">Details</Text>
          </Pressable>
          {showDetails ? (
            <View className="mt-1 rounded-md bg-inset p-3">
              {factEntries.map(([k, v]) => (
                <View key={k} className="mb-1 flex-row justify-between gap-3">
                  <Text className="flex-1 text-xs text-faint">{prettifyKey(k)}</Text>
                  <Text className="text-xs text-primary">{formatFactValue(k, v)}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
