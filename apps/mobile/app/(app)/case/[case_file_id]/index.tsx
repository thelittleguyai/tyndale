/**
 * Sub-case summary view (D5, Phase C §2 — DL-91). The permanent /case/{id} home for one sub-case:
 * a status banner + response-deadline clock, the three-number moment (re-hosted from Phase A), the
 * recovered-so-far tally (CONFIRMED) beside the identified estimate (labeled separately), the
 * needs-documents have/need checklist, the findings, the next check-in, and the gameplan (with its
 * full-screen call mode). Reached from a Record row; only rendered when ENABLE_RECORD_VIEW is on
 * (the API 404s otherwise, and this screen shows a graceful not-available state).
 */
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { CalendarClock, CheckCircle2, Circle, MessageSquare } from 'lucide-react-native';

import { CaseSummaryPayload, getCaseSummary } from '../../../../lib/api-client';
import { displayEnum } from '../../../../lib/enum-display';
import { Gameplan } from '../../../../components/record/Gameplan';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function CaseSummaryScreen() {
  const params = useLocalSearchParams<{ case_file_id: string }>();
  const caseFileId = String(params.case_file_id);
  const router = useRouter();

  const [summary, setSummary] = useState<CaseSummaryPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getCaseSummary(caseFileId)
      .then((s) => alive && setSummary(s))
      .catch((e) => alive && setError(e?.message ?? String(e)));
    return () => {
      alive = false;
    };
  }, [caseFileId]);

  if (error) {
    return (
      <View className="flex-1 items-center justify-center bg-page p-6">
        <Text className="mb-2 text-center text-base font-semibold text-primary">
          This case isn&rsquo;t available
        </Text>
        <Text className="mb-5 text-center text-sm text-secondary">
          We couldn&rsquo;t load this summary. It may have been removed, or the Record view isn&rsquo;t
          enabled for your account yet.
        </Text>
        <Pressable onPress={() => router.push('/')} className="min-h-[44px] items-center justify-center rounded-xl border border-hairline px-5 py-3">
          <Text className="text-sm font-semibold text-secondary">← Back to dashboard</Text>
        </Pressable>
      </View>
    );
  }
  if (!summary) {
    return (
      <View className="flex-1 items-center justify-center bg-page p-6">
        <Text className="text-sm text-faint">Loading your case…</Text>
      </View>
    );
  }

  const tn = summary.three_number;
  const openNeeded = summary.open_items.filter((d) => !d.have).length;

  return (
    <ScrollView className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <View className="w-full max-w-2xl self-center">
        <View className="mb-5 flex-row items-center justify-between">
          <Pressable onPress={() => router.push('/')} className="min-h-[44px] justify-center">
            <Text className="text-sm text-secondary">← Record</Text>
          </Pressable>
          <Pressable
            onPress={() => router.push(`/audit/${caseFileId}/thread` as never)}
            className="min-h-[44px] flex-row items-center gap-1.5"
          >
            <MessageSquare size={13} color="var(--c-text-secondary)" />
            <Text className="text-xs font-semibold text-secondary">Chat</Text>
          </Pressable>
        </View>

        {/* Status banner + response-deadline clock */}
        <StatusBanner summary={summary} />

        {(summary.provider || summary.service_date) ? (
          <Text className="mb-5 text-sm text-faint">
            {[summary.provider, summary.service_date].filter(Boolean).join(' · ')}
          </Text>
        ) : null}

        {/* The three-number moment card, re-hosted — or the honest needs-documents state */}
        {tn ? (
          <View className="mb-5 rounded-2xl border border-hairline bg-surface p-5">
            <Text className="mb-3 text-xs uppercase tracking-wider text-faint">
              Your three numbers
            </Text>
            <Row label="What you were billed" value={money(tn.provider_billed)} dim />
            <Row label="What your insurer says you owe" value={money(tn.eob_member_responsibility)} />
            <Row label="What you should owe" value={money(tn.tyndale_computed)} highlight last />
          </View>
        ) : (
          <View className="mb-5 rounded-2xl border border-hairline bg-surface p-5">
            <Text className="text-base font-semibold text-primary">
              We&rsquo;re not done computing your numbers yet
            </Text>
            <Text className="mt-1 text-sm leading-6 text-secondary">
              {openNeeded > 0
                ? 'To finish and lock in what you should owe, we need the documents below.'
                : 'This case is still in progress — check the chat for the latest.'}
            </Text>
          </View>
        )}

        {/* Recovered so far (CONFIRMED) beside the identified estimate (labeled separately) */}
        <View className="mb-5 flex-row gap-3">
          <Tally label="Recovered so far" value={money(summary.recovered_so_far)} hint="confirmed" tone="sage" />
          <Tally label="Identified" value={money(summary.identified_estimate)} hint="estimated" tone="muted" />
        </View>

        {/* Open items — needs-documents have/need checklist */}
        {summary.open_items.length ? (
          <View className="mb-5 rounded-2xl border border-accent bg-accent-tint p-5">
            <Text className="mb-3 text-xs uppercase tracking-wider text-accent">
              {openNeeded === 0 ? 'All documents received' : 'To finish, we need'}
            </Text>
            {summary.open_items.map((d, i) => (
              <View key={d.key} className={i > 0 ? 'mt-4 border-t border-hairline pt-4' : ''}>
                <View className="mb-1 flex-row items-start gap-2">
                  {d.have ? (
                    <CheckCircle2 size={18} color="var(--c-accent)" />
                  ) : (
                    <Circle size={18} color="var(--c-text-faint)" />
                  )}
                  <Text className={`flex-1 text-base font-bold ${d.have ? 'text-faint line-through' : 'text-primary'}`}>
                    {d.label}
                  </Text>
                </View>
                {d.have ? null : <Text className="ml-6 text-sm leading-6 text-secondary">{d.how_to_get}</Text>}
              </View>
            ))}
            <Pressable
              onPress={() => router.push({ pathname: '/upload', params: { caseId: caseFileId } })}
              className="mt-4 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
            >
              <Text className="text-center text-base font-bold text-on-accent">Add a document</Text>
            </Pressable>
          </View>
        ) : null}

        {/* The gameplan + call mode */}
        <Gameplan
          steps={summary.gameplan}
          callModeIntro={summary.call_mode_intro}
          callModeOutro={summary.call_mode_outro}
        />

        {/* Findings */}
        {summary.findings.length ? (
          <View className="mb-5">
            <Text className="mb-3 mt-2 text-xs uppercase tracking-wider text-faint">
              What we found
            </Text>
            {summary.findings.map((f) => (
              <View key={f.finding_id} className="mb-3 rounded-2xl border border-hairline bg-surface p-4">
                <View className="mb-1 flex-row items-center justify-between gap-2">
                  <Text className="flex-1 text-base font-bold text-primary">{f.title}</Text>
                  {f.dollar_impact ? (
                    <Text className="text-sm font-semibold text-accent">up to {money(f.dollar_impact)}</Text>
                  ) : null}
                </View>
                {f.claim ? <Text className="text-sm leading-6 text-secondary">{f.claim}</Text> : null}
                {f.recommendation ? (
                  <Text className="mt-2 text-sm leading-6 text-secondary">
                    <Text className="text-faint">What to do: </Text>
                    {displayEnum(f.recommendation)}
                  </Text>
                ) : null}
              </View>
            ))}
          </View>
        ) : null}

        {/* Next check-in (nudge) */}
        {summary.next_check_in_date ? (
          <View className="mb-6 flex-row items-center gap-2 rounded-2xl border border-hairline bg-surface p-4">
            <CalendarClock size={16} color="var(--c-text-secondary)" />
            <Text className="text-sm text-secondary">
              Next check-in <Text className="font-semibold text-primary">{summary.next_check_in_date}</Text> —
              I&rsquo;ll nudge you if there&rsquo;s no update.
            </Text>
          </View>
        ) : null}

        <Text className="mt-8 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
          advice.
        </Text>
      </View>
    </ScrollView>
  );
}

const BANNER_TONE: Record<string, string> = {
  audit_complete: 'border-accent bg-accent-tint',
  resolved: 'border-accent bg-accent-tint',
  audit_incomplete: 'border-warning bg-warning-tint',
  awaiting_eob_confirmation: 'border-warning bg-warning-tint',
  extraction_failed: 'border-danger bg-danger-tint',
  not_a_bill: 'border-danger bg-danger-tint',
};

function StatusBanner({ summary }: { summary: CaseSummaryPayload }) {
  const b = summary.status_banner;
  const tone = BANNER_TONE[b.status] ?? 'border-hairline bg-surface';
  const dl = b.response_deadline;
  return (
    <View className={`mb-3 rounded-2xl border p-4 ${tone}`}>
      <Text className="text-base font-bold text-primary">{b.label}</Text>
      {dl?.due_date ? (
        <Text className="mt-1 text-sm text-secondary">
          {dl.label} — respond by <Text className="font-semibold text-primary">{dl.due_date}</Text>
        </Text>
      ) : null}
    </View>
  );
}

function Row({
  label,
  value,
  highlight,
  dim,
  last,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  dim?: boolean;
  last?: boolean;
}) {
  const valueClass = highlight
    ? 'text-2xl font-bold text-accent'
    : dim
      ? 'text-base font-medium text-faint'
      : 'text-xl font-semibold text-primary';
  return (
    <View className={`${last ? '' : 'mb-3 '}flex-row items-baseline justify-between`}>
      <Text className={dim ? 'flex-1 pr-3 text-sm text-faint' : 'flex-1 pr-3 text-sm text-secondary'}>
        {label}
      </Text>
      <Text className={valueClass}>{value}</Text>
    </View>
  );
}

function Tally({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone: 'sage' | 'muted';
}) {
  return (
    <View className="flex-1 rounded-2xl border border-hairline bg-surface p-4">
      <Text className="text-xs text-faint">{label}</Text>
      <Text className={`mt-0.5 text-xl font-bold ${tone === 'sage' ? 'text-accent' : 'text-primary'}`}>
        {value}
      </Text>
      <Text className="text-[10px] uppercase tracking-wide text-faint">{hint}</Text>
    </View>
  );
}
