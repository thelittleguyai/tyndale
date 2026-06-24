/**
 * Audit-results screen (Phase 2I).
 *
 * Reached after the encounter-verification screen submits confirmations (which
 * kicks finalize_audit in the background). This screen polls GET /v1/audit/{id}
 * /status until 'audit_complete', then GETs the full audit result and renders
 * a savings-first hero, the three-number audit as supporting evidence, and the
 * humanized findings (including any encounter_mismatch findings surfaced from
 * the user's "no"/"not sure" confirmations).
 */

import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';
import { MessageSquare } from 'lucide-react-native';

import {
  AuditResult,
  ThumbsValue,
  getAudit,
  getAuditStatus,
  getCaseFeedback,
} from '../../../../lib/api-client';
import { ThumbsRating } from '../../../../components/thumbs-rating';
import { AuditProgress } from '../../../../components/audit/AuditProgress';
import { FindingCard } from '../../../../components/audit/FindingCard';

const POLL_INTERVAL_MS = 3000;
// Stable response_id for the composed-summary thumbs (distinct from findings).
const COMPOSED_RESPONSE_ID = 'composed_response';
// Treat sub-cent deltas as zero so float noise never triggers the celebration.
const DELTA_EPSILON = 0.005;

function dollars(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AuditResultScreen() {
  const params = useLocalSearchParams<{ case_file_id: string }>();
  const case_file_id = String(params.case_file_id);

  const [result, setResult] = useState<AuditResult | null>(null);
  const [status, setStatus] = useState<string>('audit_running');
  const [error, setError] = useState<string | null>(null);
  // response_id -> latest thumbs, restored from prior feedback on this case.
  const [ratings, setRatings] = useState<Record<string, ThumbsValue>>({});
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  // Restore any existing thumbs for this case so a refresh keeps them.
  useEffect(() => {
    getCaseFeedback(case_file_id)
      .then((cf) => {
        const map: Record<string, ThumbsValue> = {};
        for (const e of cf.events) {
          if (e.feedback_type === 'thumbs' && e.response_id && e.thumbs) {
            map[e.response_id] = e.thumbs; // last write wins (events are time-ordered)
          }
        }
        setRatings(map);
      })
      .catch(() => {/* non-fatal */});
  }, [case_file_id]);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const s = await getAuditStatus(case_file_id);
        if (cancelled) return;
        setStatus(s.status);
        if (s.status === 'audit_complete') {
          const r = await getAudit(case_file_id);
          if (cancelled) return;
          setResult(r);
          if (polling.current) {
            clearInterval(polling.current);
            polling.current = null;
          }
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? String(e));
      }
    }
    tick(); // immediate
    polling.current = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (polling.current) clearInterval(polling.current);
    };
  }, [case_file_id]);

  if (error) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep p-6">
        <Text className="text-base text-rose">Audit failed: {error}</Text>
      </View>
    );
  }
  if (!result) {
    return (
      <View className="flex-1 justify-center bg-navy-deep">
        <AuditProgress status={status} />
      </View>
    );
  }

  const a = result.audit;
  const delta = a.eob_member_responsibility - a.tyndale_computed;
  const foundSavings = delta > DELTA_EPSILON;
  const hasFindings = result.findings.length > 0;
  const cleanBill = !foundSavings && !hasFindings;

  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ padding: 20, paddingTop: 32 }}
    >
      <View className="w-full max-w-2xl self-center">
        <View className="mb-6 flex-row gap-2">
          <View className="min-h-[44px] items-center justify-center rounded-full bg-teal-deep px-4 py-1.5">
            <Text className="text-xs font-semibold text-white">Overview</Text>
          </View>
          <Link href={`/audit/${case_file_id}/chat`} asChild>
            <Pressable className="min-h-[44px] flex-row items-center justify-center gap-1.5 rounded-full border border-white/15 px-4 py-1.5">
              <MessageSquare size={13} color="rgba(255,255,255,0.7)" />
              <Text className="text-xs font-semibold text-white/70">Chat</Text>
            </Pressable>
          </Link>
        </View>

        {foundSavings ? (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-sage">
              We found ${dollars(delta)} you may not owe
            </Text>
            <Text className="text-base leading-6 text-white/75">
              Your insurer says you owe ${dollars(a.eob_member_responsibility)} — our math says $
              {dollars(a.tyndale_computed)}.
            </Text>
          </View>
        ) : cleanBill ? (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-white">
              Good news — this bill checks out
            </Text>
            <Text className="text-base leading-6 text-white/75">
              We compared every line against your plan and Medicare rates and didn&rsquo;t find
              anything to dispute.
            </Text>
          </View>
        ) : (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-white">
              Bill check complete
            </Text>
            <Text className="text-base leading-6 text-white/75">
              The totals line up, but we flagged a few things below worth a closer look.
            </Text>
          </View>
        )}

        <View className="mb-6 rounded-2xl border border-white/10 bg-navy-soft p-5">
          {foundSavings ? (
            <Text className="mb-3 text-xs uppercase tracking-wider text-white/40">
              How we got there
            </Text>
          ) : null}
          <ThreeNumberRow label="What you were billed" value={a.provider_billed} dim />
          <ThreeNumberRow
            label="What your insurer says you owe"
            value={a.eob_member_responsibility}
            secondary={foundSavings}
          />
          <ThreeNumberRow
            label="What you should owe"
            value={a.tyndale_computed}
            highlight
            last
          />
        </View>

        {result.summary ? (
          <View className="mb-6 rounded-2xl border border-white/10 bg-navy-soft p-5">
            <Text className="mb-2 text-xs uppercase tracking-wider text-white/40">Summary</Text>
            <Text className="text-base leading-6 text-white/90">{result.summary}</Text>
            <View className="mt-4 flex-row items-center justify-between border-t border-white/10 pt-3">
              <Text className="text-xs text-white/45">Was this helpful?</Text>
              <ThumbsRating
                target={{ type: 'response', id: COMPOSED_RESPONSE_ID }}
                caseFileId={case_file_id}
                existingRating={ratings[COMPOSED_RESPONSE_ID] ?? null}
                size={20}
              />
            </View>
          </View>
        ) : null}

        {hasFindings ? (
          <>
            <Text className="mb-2 mt-2 text-xs uppercase tracking-wider text-white/40">
              What we found
            </Text>
            <Text className="mb-3 text-sm leading-5 text-white/65">
              Most billing issues like these are fixable with a phone call or a short letter —
              Tyndale will guide you.
            </Text>
            {result.findings.map((f) => (
              <FindingCard
                key={f.finding_id}
                finding={f}
                caseFileId={case_file_id}
                existingRating={ratings[f.finding_id] ?? null}
              />
            ))}
          </>
        ) : null}

        <Text className="mt-12 text-center text-xs text-white/40">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </View>
    </ScrollView>
  );
}

function ThreeNumberRow({
  label,
  value,
  highlight,
  secondary,
  dim,
  last,
}: {
  label: string;
  value: number;
  /** The Tyndale-computed number — always the visual anchor. */
  highlight?: boolean;
  /** Supporting-evidence treatment when the savings hero is shown. */
  secondary?: boolean;
  /** "What you were billed" — least relevant once we have our own math. */
  dim?: boolean;
  last?: boolean;
}) {
  const valueClass = highlight
    ? 'text-2xl font-bold text-sage'
    : dim
      ? 'text-base font-medium text-white/55'
      : secondary
        ? 'text-lg font-semibold text-white/80'
        : 'text-xl font-semibold text-white';
  return (
    <View className={`${last ? '' : 'mb-3 '}flex-row items-baseline justify-between`}>
      <Text className={dim ? 'flex-1 pr-3 text-sm text-white/45' : 'flex-1 pr-3 text-sm text-white/70'}>
        {label}
      </Text>
      <Text className={valueClass}>
        ${value.toLocaleString(undefined, { minimumFractionDigits: 0 })}
      </Text>
    </View>
  );
}
