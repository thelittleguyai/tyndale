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
import { Link, Redirect, useLocalSearchParams, useRouter } from 'expo-router';
import { CheckCircle2, Circle, MessageSquare } from 'lucide-react-native';

import {
  AuditResult,
  Disclosure,
  EobCompleteness,
  ThumbsValue,
  confirmEobCompleteness,
  getAudit,
  getAuditStatus,
  getCaseFeedback,
  getDashboard,
  getEobCompleteness,
} from '../../../../lib/api-client';
import { recordDeepLinkTarget } from '../../../../lib/record-nav';
import { ThumbsRating } from '../../../../components/thumbs-rating';
import { AuditProgress } from '../../../../components/audit/AuditProgress';
import { FindingCard } from '../../../../components/audit/FindingCard';

const POLL_INTERVAL_MS = 3000;
// Stop polling after this long + show a "taking longer than expected" notice (Phase 3.4).
const AUDIT_POLL_TIMEOUT_MS = 120000;
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
  const [slow, setSlow] = useState(false);
  // D5 §3: when the Record is enabled, /audit/{id} is a legacy deep link — redirect to the
  // canonical sub-case surface (summary if results-bearing, else thread). Non-blocking: the
  // classic screen renders immediately and this only fires when the flag resolves on, so the
  // shipping flag-off path pays nothing (flag-off IS the transition, D7).
  const [recordTarget, setRecordTarget] = useState<string | null>(null);
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
    let alive = true;
    (async () => {
      try {
        const [dash, st] = await Promise.all([getDashboard(), getAuditStatus(case_file_id)]);
        if (alive) {
          setRecordTarget(recordDeepLinkTarget(case_file_id, st.status, dash.record_enabled ?? false));
        }
      } catch {
        /* fail open — render the classic audit screen */
      }
    })();
    return () => {
      alive = false;
    };
  }, [case_file_id]);

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();
    async function tick() {
      if (Date.now() - startedAt > AUDIT_POLL_TIMEOUT_MS) {
        if (!cancelled) setSlow(true);
        if (polling.current) {
          clearInterval(polling.current);
          polling.current = null;
        }
        return;
      }
      try {
        const s = await getAuditStatus(case_file_id);
        if (cancelled) return;
        setStatus(s.status);
        // Both are terminal — audit_incomplete is a real end state (budget/degrade), not a
        // stall to keep polling (Item 1): fetch the partial result and stop.
        if (s.status === 'audit_complete' || s.status === 'audit_incomplete') {
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

  // D5 §3: hand off to the Record's canonical surface when the flag is on (see recordTarget above).
  if (recordTarget) {
    return <Redirect href={recordTarget as never} />;
  }

  if (error) {
    return (
      <View className="flex-1 items-center justify-center bg-page p-6">
        <Text className="text-base text-danger">Audit failed: {error}</Text>
      </View>
    );
  }
  if (slow && !result) {
    return (
      <View className="flex-1 items-center justify-center bg-page p-6">
        <Text className="mb-2 text-center text-base font-semibold text-primary">
          This is taking longer than expected
        </Text>
        <Text className="text-center text-body text-secondary">
          Your audit is still running. Check back in a few minutes — we&apos;ll have your results
          ready.
        </Text>
      </View>
    );
  }
  if (!result) {
    return (
      <View className="flex-1 justify-center bg-page">
        <AuditProgress status={status} />
      </View>
    );
  }

  // Terminal partial state (HP-1): distinguish an honest, user-actionable needs_documents result
  // (the audit found things but is blocked on missing inputs) from a system_error (budget /
  // citation / provider / crash). Only system_error shows failure/apology copy — everything else
  // incomplete gets the positive "here's what we found; to finish we need…" screen.
  if (result.status === 'audit_incomplete' || result.incomplete_reason || !result.audit) {
    return result.incomplete_reason === 'system_error' ? (
      <SystemError result={result} caseFileId={case_file_id} />
    ) : (
      <NeedsDocuments result={result} caseFileId={case_file_id} />
    );
  }

  const a = result.audit;
  const delta = a.eob_member_responsibility - a.tyndale_computed;
  const foundSavings = delta > DELTA_EPSILON;
  const hasFindings = result.findings.length > 0;
  const cleanBill = !foundSavings && !hasFindings;

  return (
    <ScrollView
      className="flex-1 bg-page"
      contentContainerStyle={{ padding: 20, paddingTop: 32 }}
    >
      <View className="w-full max-w-2xl self-center">
        <View className="mb-6 flex-row gap-2">
          <View className="min-h-[44px] items-center justify-center rounded-full bg-surface-raised px-4 py-1.5">
            <Text className="text-xs font-semibold text-primary">Overview</Text>
          </View>
          <Link href={`/audit/${case_file_id}/chat`} asChild>
            <Pressable className="min-h-[44px] flex-row items-center justify-center gap-1.5 rounded-full border border-hairline px-4 py-1.5">
              <MessageSquare size={13} color="var(--c-text-secondary)" />
              <Text className="text-xs font-semibold text-secondary">Chat</Text>
            </Pressable>
          </Link>
        </View>

        <EobCompletenessCard caseFileId={case_file_id} />

        {foundSavings ? (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-accent">
              We found ${dollars(delta)} you may not owe
            </Text>
            <Text className="text-base leading-6 text-secondary">
              Your insurer says you owe ${dollars(a.eob_member_responsibility)} — our math says $
              {dollars(a.tyndale_computed)}.
            </Text>
          </View>
        ) : cleanBill ? (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-primary">
              Good news — this bill checks out
            </Text>
            <Text className="text-base leading-6 text-secondary">
              We compared every line against your plan and Medicare rates and didn&rsquo;t find
              anything to dispute.
            </Text>
          </View>
        ) : (
          <View className="mb-6">
            <Text className="mb-3 text-3xl font-bold leading-tight text-primary">
              Bill check complete
            </Text>
            <Text className="text-base leading-6 text-secondary">
              The totals line up, but we flagged a few things below worth a closer look.
            </Text>
          </View>
        )}

        <View className="mb-6 rounded-2xl border border-hairline bg-surface p-5">
          {foundSavings ? (
            <Text className="mb-3 text-xs text-faint">
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

        <ChaseCard disclosure={result.disclosure} />

        {result.summary ? (
          <View className="mb-6 rounded-2xl border border-hairline bg-surface p-5">
            <Text className="mb-2 text-xs text-faint">Summary</Text>
            <Text className="text-base leading-6 text-primary">{result.summary}</Text>
            <View className="mt-4 flex-row items-center justify-between border-t border-hairline pt-3">
              <Text className="text-xs text-faint">Was this helpful?</Text>
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
            <Text className="mb-2 mt-2 text-xs text-faint">
              What we found
            </Text>
            <Text className="mb-3 text-body leading-6 text-secondary">
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

        <Text className="mt-12 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </View>
    </ScrollView>
  );
}

/** EOB-completeness confirmation (DL-86): "does that look like all of them?" — shown until
 * the user answers, so the audit never treats a partial pile of EOBs as the whole picture. */
function EobCompletenessCard({ caseFileId }: { caseFileId: string }) {
  const [summary, setSummary] = useState<EobCompleteness | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    getEobCompleteness(caseFileId)
      .then((s) => alive && setSummary(s))
      .catch(() => {/* non-fatal — the card just won't show */});
    return () => {
      alive = false;
    };
  }, [caseFileId]);

  const answer = async (allUploaded: boolean) => {
    setBusy(true);
    try {
      setSummary(await confirmEobCompleteness(caseFileId, allUploaded));
    } catch {
      setBusy(false);
    }
  };

  // Nothing to confirm (no EOBs) or already answered → render nothing.
  if (!summary || summary.eob_count === 0 || summary.confirmed !== null) return null;

  return (
    <View className="mb-6 rounded-2xl border border-hairline bg-surface p-5">
      <Text className="mb-1 text-xs text-faint">
        Before we finish
      </Text>
      <Text className="mb-4 text-base leading-6 text-primary">{summary.question}</Text>
      <View className="flex-row gap-3">
        <Pressable
          disabled={busy}
          onPress={() => answer(true)}
          className="flex-1 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
        >
          <Text className="text-body font-bold text-on-accent">Yes, that&apos;s all of them</Text>
        </Pressable>
        <Pressable
          disabled={busy}
          onPress={() => answer(false)}
          className="flex-1 min-h-[44px] items-center justify-center rounded-xl border border-hairline px-4 py-3 hover:bg-inset"
        >
          <Text className="text-body font-semibold text-secondary">I have more</Text>
        </Pressable>
      </View>
    </View>
  );
}

// Missing inputs the disclosure ladder wants chased map to the document that resolves them.
const CHASE_DOC_LABELS: Record<string, string> = {
  deductible_amount: "your plan's Summary of Benefits (the SBC)",
  oop_max_amount: "your plan's Summary of Benefits (the SBC)",
  coinsurance_percent: "your plan's Summary of Benefits (the SBC)",
  copay_specialist: "your plan's Summary of Benefits (the SBC)",
  copay_er: "your plan's Summary of Benefits (the SBC)",
};

/** Tier-3 disclosure (DL-85): a document the user should find to collapse a chase-sized
 * uncertainty range. One minimal card state; renders nothing below tier 3. */
function ChaseCard({ disclosure }: { disclosure?: Disclosure | null }) {
  if (!disclosure || disclosure.tier < 3 || disclosure.chase_inputs.length === 0) return null;
  const docs = Array.from(
    new Set(disclosure.chase_inputs.map((k) => CHASE_DOC_LABELS[k] ?? 'your plan documents')),
  );
  return (
    <View className="mb-6 rounded-2xl border border-warning bg-warning-tint p-5">
      <Text className="mb-1 text-body font-bold text-warning">One thing would sharpen this</Text>
      <Text className="text-body leading-6 text-secondary">
        A few plan details were missing, so these numbers are an estimated range. To pin them
        down, find {docs.join(' and ')} and add it — I&apos;ll rerun the math with the real
        figures.
      </Text>
    </View>
  );
}

/** needs_documents (HP-1): the audit RAN and found things, but the three-number computation is
 * blocked on missing inputs. POSITIVE framing — what we found so far + the document checklist to
 * finish. No failure language, no "team has been notified". */
export function NeedsDocuments({ result, caseFileId }: { result: AuditResult; caseFileId: string }) {
  const router = useRouter();
  const docs = result.documents_needed ?? [];
  const remaining = docs.filter((d) => !d.have).length;
  return (
    <ScrollView className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <View className="w-full max-w-2xl self-center">
        <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
          <Text className="text-sm text-secondary">← Back to dashboard</Text>
        </Pressable>

        <Text className="mb-3 text-2xl font-bold leading-tight text-primary">
          Here&rsquo;s what we found so far
        </Text>
        <Text className="mb-6 text-base leading-6 text-secondary">
          We&rsquo;ve started your audit. To finish it and lock in the numbers, we need a couple of
          documents from you — here&rsquo;s how to get each one.
        </Text>

        {docs.length ? (
          <View className="mb-6 rounded-2xl border border-accent bg-accent-tint p-5">
            <Text className="mb-3 text-xs text-accent">
              {remaining === 0 ? 'All set — re-checking your audit' : 'To finish your audit, we need'}
            </Text>
            {docs.map((d, i) => (
              <View key={d.key} className={i > 0 ? 'mt-4 border-t border-hairline pt-4' : ''}>
                <View className="mb-1 flex-row items-start gap-2">
                  {d.have ? (
                    <CheckCircle2 size={18} color="var(--c-accent)" />
                  ) : (
                    <Circle size={18} color="var(--c-text-faint)" />
                  )}
                  <Text
                    className={`flex-1 text-base font-bold ${d.have ? 'text-faint line-through' : 'text-primary'}`}
                  >
                    {d.label}
                  </Text>
                </View>
                {d.have ? null : (
                  <Text className="ml-6 text-body leading-6 text-secondary">{d.how_to_get}</Text>
                )}
              </View>
            ))}
          </View>
        ) : null}

        <Pressable
          onPress={() =>
            router.push({ pathname: '/upload', params: { caseId: caseFileId } })
          }
          className="mb-8 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
        >
          <Text className="text-center text-base font-bold text-on-accent">Add a document</Text>
        </Pressable>

        {result.findings.length ? (
          <>
            <Text className="mb-2 mt-2 text-xs text-faint">
              What we&rsquo;ve found so far
            </Text>
            <Text className="mb-3 text-body leading-6 text-secondary">
              These are worth acting on now — Tyndale will guide you.
            </Text>
            {result.findings.map((f) => (
              <FindingCard key={f.finding_id} finding={f} caseFileId={caseFileId} existingRating={null} />
            ))}
          </>
        ) : null}

        <Text className="mt-12 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </View>
    </ScrollView>
  );
}

/** system_error (HP-1): budget / citation gate / provider failure / crash — NOT user-actionable.
 * The apology copy, and the ONLY screen that says "our team has been notified" (a real alert was
 * emitted server-side). Any partial numbers/findings still show so nothing is dead-ended. */
function SystemError({ result, caseFileId }: { result: AuditResult; caseFileId: string }) {
  const router = useRouter();
  const a = result.audit;
  return (
    <ScrollView className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <View className="w-full max-w-2xl self-center">
        <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
          <Text className="text-sm text-secondary">← Back to dashboard</Text>
        </Pressable>

        <Text className="mb-3 text-2xl font-bold leading-tight text-primary">
          We couldn&rsquo;t finish this audit
        </Text>
        <Text className="mb-6 text-base leading-6 text-secondary">
          {a
            ? 'We ran the numbers but couldn’t finish the written summary this time — our team has been notified and will take a look. Here’s what we computed.'
            : 'Something went wrong on our end this time — our team has been notified. We’ll follow up once it’s sorted; you don’t need to do anything.'}
        </Text>

        {a ? (
          <View className="mb-6 rounded-2xl border border-hairline bg-surface p-5">
            <Text className="mb-3 text-xs text-faint">What we computed</Text>
            <ThreeNumberRow label="What you were billed" value={a.provider_billed} dim />
            <ThreeNumberRow label="What your insurer says you owe" value={a.eob_member_responsibility} />
            <ThreeNumberRow label="What you should owe" value={a.tyndale_computed} highlight last />
          </View>
        ) : null}

        {result.findings.length ? (
          <>
            <Text className="mb-2 mt-2 text-xs text-faint">What we found</Text>
            {result.findings.map((f) => (
              <FindingCard key={f.finding_id} finding={f} caseFileId={caseFileId} existingRating={null} />
            ))}
          </>
        ) : null}

        <Text className="mt-12 text-center text-xs text-faint">
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
    ? 'text-2xl font-bold text-accent'
    : dim
      ? 'text-base font-medium text-faint'
      : secondary
        ? 'text-lg font-semibold text-secondary'
        : 'text-xl font-semibold text-primary';
  return (
    <View className={`${last ? '' : 'mb-3 '}flex-row items-baseline justify-between`}>
      <Text className={dim ? 'flex-1 pr-3 text-body text-faint' : 'flex-1 pr-3 text-body text-secondary'}>
        {label}
      </Text>
      <Text className={valueClass}>
        ${value.toLocaleString(undefined, { minimumFractionDigits: 0 })}
      </Text>
    </View>
  );
}
