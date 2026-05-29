/**
 * Walking-skeleton audit-results screen.
 *
 * Polls GET /v1/audit/{case_file_id} every 3s until status is 'complete', then
 * renders the three-number audit + findings list + the Lead Planner's composed
 * summary. Phase 2H replaces this with the full dashboard binding + encounter
 * verification UI.
 */

import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { AuditResult, FindingOut, getAudit, postAudit } from '../../../lib/api-client';

const POLL_INTERVAL_MS = 3000;

export default function AuditScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ case_file_id: string }>();
  const case_file_id = String(params.case_file_id);

  const [result, setResult] = useState<AuditResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kicked, setKicked] = useState(false);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  // Kick off the audit once when this screen mounts.
  useEffect(() => {
    if (kicked) return;
    setKicked(true);
    postAudit(case_file_id)
      .then((r) => setResult(r))
      .catch((e) => setError(e?.message ?? String(e)));
  }, [case_file_id, kicked]);

  // Poll until complete.
  useEffect(() => {
    if (!result || result.status === 'complete') return;
    polling.current = setInterval(async () => {
      try {
        const r = await getAudit(case_file_id);
        setResult(r);
        if (r.status === 'complete' && polling.current) {
          clearInterval(polling.current);
          polling.current = null;
        }
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    }, POLL_INTERVAL_MS);
    return () => {
      if (polling.current) clearInterval(polling.current);
    };
  }, [case_file_id, result]);

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
        <Text className="mt-4 text-sm text-white/60">Opening case…</Text>
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
      <Text className="mb-6 text-xs text-white/40">case {case_file_id.slice(0, 8)}…</Text>

      {/* Three-number audit (Tier A facts) */}
      <View className="mb-6 rounded-2xl border border-white/10 bg-navy-mid p-5">
        <ThreeNumberRow label="What you were billed" value={a.provider_billed} />
        <ThreeNumberRow
          label="What your insurer says you owe"
          value={a.eob_member_responsibility}
        />
        <ThreeNumberRow
          label="What you should owe"
          value={a.tyndale_computed}
          highlight
        />
      </View>

      {/* Composed Lead-Planner summary */}
      {result.summary ? (
        <View className="mb-6 rounded-2xl border border-white/10 bg-navy-mid p-5">
          <Text className="mb-2 text-xs uppercase tracking-wider text-white/40">
            Summary
          </Text>
          <Text className="text-base leading-6 text-white/90">{result.summary}</Text>
        </View>
      ) : null}

      {/* Findings */}
      <Text className="mb-2 mt-2 text-xs uppercase tracking-wider text-white/40">
        Findings
      </Text>
      {result.findings.length === 0 ? (
        <Text className="text-sm text-white/60">No findings recorded yet.</Text>
      ) : (
        result.findings.map((f) => <FindingCard key={f.finding_id} finding={f} />)
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
        className={
          highlight
            ? 'text-2xl font-bold text-sage'
            : 'text-xl font-semibold text-white'
        }
      >
        ${value.toLocaleString(undefined, { minimumFractionDigits: 0 })}
      </Text>
    </View>
  );
}

function FindingCard({ finding }: { finding: FindingOut }) {
  const tier = finding.voice_tier;
  const claim =
    typeof finding.legal_claim === 'object' && finding.legal_claim
      ? (finding.legal_claim as any).claim ?? null
      : null;
  const marker =
    typeof finding.legal_claim === 'object' && finding.legal_claim
      ? (finding.legal_claim as any).marker ?? null
      : null;
  const action =
    typeof finding.recommendation === 'object' && finding.recommendation
      ? (finding.recommendation as any).action ?? null
      : null;
  const reasoning =
    typeof finding.recommendation === 'object' && finding.recommendation
      ? (finding.recommendation as any).reasoning ?? null
      : null;

  return (
    <View className="mb-3 rounded-2xl border border-white/10 bg-navy-mid p-4">
      <View className="mb-2 flex-row items-center justify-between">
        <Text className="text-xs uppercase tracking-wider text-white/40">
          {finding.finding_type.replace('_', ' ')} · {finding.category}
        </Text>
        <View
          className={
            tier === 'A'
              ? 'rounded-md bg-white/10 px-2 py-0.5'
              : tier === 'B'
                ? 'rounded-md bg-sage/20 px-2 py-0.5'
                : 'rounded-md bg-amber/20 px-2 py-0.5'
          }
        >
          <Text className="text-[10px] font-semibold tracking-wider text-white">
            TIER {tier}
          </Text>
        </View>
      </View>

      {claim ? (
        <Text className="mb-2 text-sm text-white/90">
          {claim}
          {marker ? <Text className="text-xs text-white/50"> {marker}</Text> : null}
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

      {action ? (
        <View className="mt-1">
          <Text className="text-xs uppercase tracking-wider text-white/40">
            Recommended next action
          </Text>
          <Text className="mt-1 text-sm text-white/90">{action}</Text>
          {reasoning ? (
            <Text className="mt-1 text-xs text-white/60">{reasoning}</Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
