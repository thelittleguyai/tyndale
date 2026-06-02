/**
 * Audit-results screen (Phase 2I).
 *
 * Reached after the encounter-verification screen submits confirmations (which
 * kicks finalize_audit in the background). This screen polls GET /v1/audit/{id}
 * /status until 'audit_complete', then GETs the full audit result and renders
 * the three-number audit + findings (including any encounter_mismatch findings
 * surfaced from the user's "no"/"not sure" confirmations).
 */

import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';
import { MessageSquare } from 'lucide-react-native';

import {
  AuditResult,
  FindingOut,
  ThumbsValue,
  getAudit,
  getAuditStatus,
  getCaseFeedback,
} from '../../../../lib/api-client';
import { ThumbsRating } from '../../../../components/thumbs-rating';

const POLL_INTERVAL_MS = 3000;
// Stable response_id for the composed-summary thumbs (distinct from findings).
const COMPOSED_RESPONSE_ID = 'composed_response';

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
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#fff" />
        <Text className="mt-4 text-sm text-white/60">
          {status === 'audit_running' ? 'Running your audit…' : `Status: ${status}`}
        </Text>
      </View>
    );
  }

  const a = result.audit;
  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ padding: 20, paddingTop: 32 }}
    >
      <Text className="mb-1 text-3xl font-bold text-white">Bill check complete</Text>
      <Text className="mb-4 text-xs text-white/40">case {case_file_id.slice(0, 8)}…</Text>

      <View className="mb-6 flex-row gap-2">
        <View className="rounded-full bg-teal-deep px-4 py-1.5">
          <Text className="text-xs font-semibold text-white">Overview</Text>
        </View>
        <Link href={`/audit/${case_file_id}/chat`} asChild>
          <Pressable className="flex-row items-center gap-1.5 rounded-full border border-white/15 px-4 py-1.5">
            <MessageSquare size={13} color="rgba(255,255,255,0.7)" />
            <Text className="text-xs font-semibold text-white/70">Chat</Text>
          </Pressable>
        </Link>
      </View>

      <View className="mb-6 rounded-2xl border border-white/10 bg-navy-soft p-5">
        <ThreeNumberRow label="What you were billed" value={a.provider_billed} />
        <ThreeNumberRow
          label="What your insurer says you owe"
          value={a.eob_member_responsibility}
        />
        <ThreeNumberRow label="What you should owe" value={a.tyndale_computed} highlight />
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

      <Text className="mb-2 mt-2 text-xs uppercase tracking-wider text-white/40">Findings</Text>
      {result.findings.length === 0 ? (
        <Text className="text-sm text-white/60">No findings recorded.</Text>
      ) : (
        result.findings.map((f) => (
          <FindingCard
            key={f.finding_id}
            finding={f}
            caseFileId={case_file_id}
            existingRating={ratings[f.finding_id] ?? null}
          />
        ))
      )}

      <Text className="mt-12 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </ScrollView>
  );
}

function ThreeNumberRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <View className="mb-3 flex-row items-baseline justify-between">
      <Text className="flex-1 pr-3 text-sm text-white/70">{label}</Text>
      <Text
        className={highlight ? 'text-2xl font-bold text-sage' : 'text-xl font-semibold text-white'}
      >
        ${value.toLocaleString(undefined, { minimumFractionDigits: 0 })}
      </Text>
    </View>
  );
}

function FindingCard({
  finding,
  caseFileId,
  existingRating,
}: {
  finding: FindingOut;
  caseFileId: string;
  existingRating: ThumbsValue | null;
}) {
  const tier = finding.voice_tier;
  const lc = (finding.legal_claim ?? {}) as any;
  const rec = (finding.recommendation ?? {}) as any;
  const isMismatch = finding.finding_type === 'encounter_mismatch';

  return (
    <View
      className={
        isMismatch
          ? 'mb-3 rounded-2xl border border-rose/40 bg-navy-soft p-4'
          : 'mb-3 rounded-2xl border border-white/10 bg-navy-soft p-4'
      }
    >
      <View className="mb-2 flex-row items-center justify-between">
        <Text className="flex-1 pr-2 text-xs uppercase tracking-wider text-white/40">
          {finding.finding_type.replace(/_/g, ' ')} · {finding.category}
        </Text>
        <View className="flex-row items-center gap-2">
          <View
            className={
              tier === 'A'
                ? 'rounded-md bg-white/10 px-2 py-0.5'
                : tier === 'B'
                  ? 'rounded-md bg-sage/20 px-2 py-0.5'
                  : 'rounded-md bg-amber/20 px-2 py-0.5'
            }
          >
            <Text className="text-[10px] font-semibold tracking-wider text-white">TIER {tier}</Text>
          </View>
          <ThumbsRating
            target={{ type: 'finding', id: finding.finding_id }}
            caseFileId={caseFileId}
            existingRating={existingRating}
            size={15}
          />
        </View>
      </View>

      {lc.claim ? (
        <Text className="mb-2 text-sm text-white/90">
          {lc.claim}
          {lc.marker ? <Text className="text-xs text-white/50"> {lc.marker}</Text> : null}
        </Text>
      ) : null}

      {finding.facts && Object.keys(finding.facts).length > 0 ? (
        <View className="mb-2 rounded-md bg-black/20 p-2">
          {Object.entries(finding.facts).map(([k, v]) => (
            <Text key={k} className="text-xs text-white/70">
              {k}: <Text className="text-white">{String(v)}</Text>
            </Text>
          ))}
        </View>
      ) : null}

      {rec.action ? (
        <View className="mt-1">
          <Text className="text-xs uppercase tracking-wider text-white/40">
            Recommended next action
          </Text>
          <Text className="mt-1 text-sm text-white/90">{rec.action}</Text>
          {rec.reasoning ? (
            <Text className="mt-1 text-xs text-white/60">{rec.reasoning}</Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
