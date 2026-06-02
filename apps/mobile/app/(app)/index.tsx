/**
 * Signed-in dashboard — Phase 2H pixel-faithful to
 * docs/design/signed_in_dashboard.png.
 *
 * Wires the four state branches the prompt calls out:
 *   - loading:    skeleton shimmer on the coverage tiles + "Loading your
 *                 dashboard" under the hero
 *   - empty:      coverage tiles show an inline "Upload your insurance card
 *                 to populate" CTA that routes to /upload
 *   - populated:  full dashboard renders with real numbers
 *   - lead-with-status: when open_cases is non-empty AND
 *                 status_forward_greeting is set, the hero card shows that
 *                 instead of "Welcome back, {first_name}." (Change Order
 *                 001 item 3).
 *
 * Real auth is Phase 2K — the dev-mode auth stub on the backend means the
 * dashboard renders end-to-end without any sign-in plumbing here.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  Home,
  MessageSquare,
  Plus,
  Search,
  ShieldCheck,
  User as UserIcon,
} from 'lucide-react-native';

import {
  getDashboard,
  getUserProfile,
  makeFeedbackEvent,
  submitFeedback,
  type DashboardPayload,
  type ResolvedValue,
} from '../../lib/api-client';
import { HeroMotif } from '../../components/hero-motif';

const formatUSD = (n: number) =>
  '$' + n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function DashboardScreen() {
  const router = useRouter();
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const d = await getDashboard();
      setData(d);
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Header firstName={data?.user.first_name ?? 'there'} />

      <View className="px-5 pt-3">
        <Hero
          firstName={data?.user.first_name ?? 'there'}
          statusGreeting={data?.status_forward_greeting ?? null}
          loading={loading && !data}
        />

        <CoverageRow1
          deductible={data?.coverage.deductible ?? null}
          oopMax={data?.coverage.oop_max ?? null}
          extractionStatus={data?.coverage.extraction_status ?? 'missing'}
          loading={loading && !data}
          onUploadPress={() => router.push('/upload')}
        />

        <CoverageRow2
          copays={data?.coverage.copays ?? null}
          amountSaved={data?.amount_saved_ytd ?? 0}
          loading={loading && !data}
        />

        <Text className="mb-3 mt-6 text-xs uppercase tracking-widest text-white/45">
          Quick Actions
        </Text>
        <View className="flex-row flex-wrap gap-3">
          <QuickActionTile
            title="Check a Bill"
            subtitle="Review and manage your recent statements and payments."
            Icon={FileText}
            onPress={() => router.push('/upload')}
          />
          <QuickActionTile
            title="Plan a Visit"
            subtitle="Schedule appointments and manage your upcoming care."
            Icon={Calendar}
            onPress={() => router.push('/plan-a-visit-placeholder')}
          />
          <QuickActionTile
            title="Find a Doctor"
            subtitle="Search in-network providers and specialists near you."
            Icon={Search}
            onPress={() => router.push('/find-a-doctor-placeholder')}
          />
          <QuickActionTile
            title="Estimate Costs"
            subtitle="Get transparent pricing and coverage estimates before care."
            Icon={Clock}
            onPress={() => router.push('/estimate-costs-placeholder')}
          />
        </View>

        {(data?.outcome_prompts ?? []).length > 0 ? (
          <OutcomeFollowupCard prompt={data!.outcome_prompts[0]} onDone={load} />
        ) : null}

        <ChatCTA onPress={() => router.push('/chat-placeholder')} />

        {error ? (
          <Text className="mt-4 text-xs text-rose">Dashboard fetch error: {error}</Text>
        ) : null}

        <Text className="mt-10 text-center text-xs text-white/40">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </View>
    </ScrollView>
  );
}

// ─── Outcome follow-up (Phase 2J) ────────────────────────────────────────────
function OutcomeFollowupCard({
  prompt,
  onDone,
}: {
  prompt: { case_file_id: string; days_since_recommendation: number; finding_summary: string };
  onDone: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  const answer = async (resolved: ResolvedValue) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await submitFeedback(
        makeFeedbackEvent({
          case_file_id: prompt.case_file_id,
          feedback_type: 'outcome_report',
          outcome: { resolved },
        }),
      );
      onDone(); // server stamped last_outcome_check_at; reload drops the card
    } catch {
      setSubmitting(false);
    }
  };

  const skip = async () => {
    if (submitting) return;
    setSubmitting(true);
    // "Skip for now" still stamps last_outcome_check_at via an outcome_report
    // with resolved='pending' so the card stops nagging this cycle.
    try {
      await submitFeedback(
        makeFeedbackEvent({
          case_file_id: prompt.case_file_id,
          feedback_type: 'outcome_report',
          outcome: { resolved: 'pending' },
        }),
      );
      onDone();
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <View className="mt-6 rounded-2xl border border-amber/30 bg-navy-soft p-5">
      <View className="mb-2 flex-row items-center gap-3">
        <View className="h-9 w-9 items-center justify-center rounded-md bg-amber/20">
          <Clock size={18} color="#E08A3C" />
        </View>
        <Text className="text-base font-bold text-white">Quick check-in: how did it go?</Text>
      </View>
      <Text className="mb-4 text-sm leading-6 text-white/70">
        {prompt.days_since_recommendation} days ago I helped you with {prompt.finding_summary}. Did
        it get resolved?
      </Text>
      <View className="flex-row flex-wrap gap-2">
        <OutcomeButton label="Yes, resolved" tone="sage" onPress={() => answer('yes')} />
        <OutcomeButton label="Partially" tone="amber" onPress={() => answer('partial')} />
        <OutcomeButton label="No / not yet" tone="rose" onPress={() => answer('no')} />
        <OutcomeButton label="Skip for now" tone="ink" onPress={skip} />
      </View>
    </View>
  );
}

function OutcomeButton({
  label,
  tone,
  onPress,
}: {
  label: string;
  tone: 'sage' | 'amber' | 'rose' | 'ink';
  onPress: () => void;
}) {
  const cls =
    tone === 'sage'
      ? 'bg-sage'
      : tone === 'amber'
        ? 'bg-amber'
        : tone === 'rose'
          ? 'bg-rose'
          : 'bg-white/10';
  const textCls = tone === 'ink' ? 'text-white/70' : 'text-ink';
  return (
    <Pressable onPress={onPress} className={`rounded-lg px-3 py-2 ${cls}`}>
      <Text className={`text-xs font-bold ${textCls}`}>{label}</Text>
    </Pressable>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────
// The separate admin console (CO-9) lives at its own IP-allowlisted subdomain.
const ADMIN_CONSOLE_URL = 'https://admin.tyndaleapp.net';

function Header({ firstName }: { firstName: string }) {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);

  // The Admin pill is admin-only: DL-60 anti-enumeration means non-admins must
  // never even see that an admin surface exists. It deep-links out to the
  // standalone console (Linking.openURL → new tab on web, system browser on
  // native). That console is IP-allowlisted, so it only loads on an allowed
  // network — the pill is a convenience jump-off, not an in-app screen.
  useEffect(() => {
    getUserProfile()
      .then((p) => setIsAdmin(p?.user_type === 'admin'))
      .catch(() => setIsAdmin(false));
  }, []);

  return (
    <View className="flex-row items-center justify-between bg-navy-soft px-5 py-3">
      <View className="flex-row items-center gap-2">
        <View className="h-7 w-7 items-center justify-center rounded-md bg-teal-deep">
          <View className="h-3.5 w-3.5 rounded-sm bg-cream" />
        </View>
        <Text className="text-base font-bold text-white">Tyndale</Text>
      </View>
      <View className="flex-row items-center gap-2">
        {isAdmin ? (
          <Pressable
            onPress={() => {
              Linking.openURL(ADMIN_CONSOLE_URL).catch(() => {});
            }}
            accessibilityRole="button"
            accessibilityHint="Opens the Tyndale admin console in a new tab"
            className="flex-row items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5"
          >
            <ShieldCheck size={14} color="rgba(255,255,255,0.7)" />
            <Text className="text-xs font-semibold text-white/80">Admin</Text>
          </Pressable>
        ) : null}
        <Pressable
          onPress={() => router.push('/settings')}
          accessibilityRole="button"
          className="flex-row items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-2.5 py-1.5"
        >
          <View className="h-5 w-5 items-center justify-center rounded-full bg-amber/80">
            <Text className="text-[10px] font-bold text-ink">
              {firstName.charAt(0).toUpperCase()}
            </Text>
          </View>
          <Text className="text-xs font-medium text-white/90">{firstName} Fluegel</Text>
        </Pressable>
        <Pressable
          onPress={() => router.replace('/sign-in')}
          className="rounded-full bg-white/5 px-3 py-1.5"
        >
          <Text className="text-xs font-semibold text-white/80">Sign Out</Text>
        </Pressable>
      </View>
    </View>
  );
}

// ─── Hero ───────────────────────────────────────────────────────────────────
function Hero({
  firstName,
  statusGreeting,
  loading,
}: {
  firstName: string;
  statusGreeting: string | null;
  loading: boolean;
}) {
  return (
    <View className="relative overflow-hidden rounded-2xl bg-teal-deep px-5 py-7">
      <View className="absolute -right-6 -top-6 opacity-80">
        <HeroMotif size={170} />
      </View>
      <View className="relative z-10 pr-32">
        {statusGreeting ? (
          <Text className="text-2xl font-bold leading-snug text-white">
            {statusGreeting}
          </Text>
        ) : (
          <>
            <Text className="text-3xl font-bold leading-tight text-white">
              Welcome back,
            </Text>
            <Text className="text-3xl font-bold leading-tight text-white">
              {firstName}.
            </Text>
          </>
        )}
        <Text className="mt-3 text-sm text-white/80">
          {loading ? 'Loading your dashboard…' : 'What would you like to do today?'}
        </Text>
      </View>
    </View>
  );
}

// ─── Coverage row 1 — Deductible + OOP Max ─────────────────────────────────
function CoverageRow1({
  deductible,
  oopMax,
  extractionStatus,
  loading,
  onUploadPress,
}: {
  deductible: { total: number; met: number; remaining: number } | null;
  oopMax: { total: number; met: number; remaining: number } | null;
  extractionStatus: string;
  loading: boolean;
  onUploadPress: () => void;
}) {
  if (loading) {
    return (
      <View className="mt-4 flex-row gap-3">
        <SkeletonTile className="flex-1 h-24" />
        <SkeletonTile className="flex-1 h-24" />
      </View>
    );
  }
  if (extractionStatus === 'missing') {
    return (
      <View className="mt-4 rounded-xl border border-dashed border-white/15 bg-white/5 p-5">
        <Text className="text-sm font-semibold text-white">No coverage on file yet</Text>
        <Text className="mt-1 text-xs text-white/60">
          Upload your insurance card so Tyndale can populate your deductible, out-of-pocket
          max, and copays here.
        </Text>
        <Pressable
          onPress={onUploadPress}
          className="mt-3 self-start rounded-md bg-sage px-3 py-2"
        >
          <Text className="text-xs font-bold text-ink">Upload insurance card</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <View className="mt-4 flex-row gap-3">
      <CoverageTile
        label="Deductible"
        meter={deductible}
        progressClass="bg-sage"
      />
      <CoverageTile
        label="Out-of-Pocket Max"
        meter={oopMax}
        progressClass="bg-amber"
      />
    </View>
  );
}

function CoverageTile({
  label,
  meter,
  progressClass,
}: {
  label: string;
  meter: { total: number; met: number; remaining: number } | null;
  progressClass: string;
}) {
  if (!meter) {
    return (
      <View className="flex-1 rounded-xl bg-white p-4">
        <Text className="text-sm font-semibold text-ink">{label}</Text>
        <Text className="mt-2 text-xs text-ink/60">Pending extraction…</Text>
      </View>
    );
  }
  const pct = Math.max(0, Math.min(1, meter.total > 0 ? meter.met / meter.total : 0));
  return (
    <View className="flex-1 rounded-xl bg-white p-4">
      <View className="flex-row items-baseline justify-between">
        <Text className="text-sm font-semibold text-ink">{label}</Text>
        <Text className="text-sm font-semibold text-ink">
          {formatUSD(meter.met)} / {formatUSD(meter.total)}
        </Text>
      </View>
      <View className="mt-3 h-1.5 overflow-hidden rounded-full bg-line">
        <View
          className={`h-full ${progressClass}`}
          style={{ width: `${pct * 100}%` }}
        />
      </View>
      <View className="mt-2 flex-row items-baseline justify-between">
        <Text className="text-xs text-ink/60">Amount Spent: {formatUSD(meter.met)}</Text>
        <Text className="text-xs font-semibold text-sage-deep">
          {formatUSD(meter.remaining)} remaining
        </Text>
      </View>
    </View>
  );
}

// ─── Coverage row 2 — 3 copays + Amount Saved YTD ──────────────────────────
function CoverageRow2({
  copays,
  amountSaved,
  loading,
}: {
  copays: {
    pcp_visit: { amount: number };
    er_visit: { amount: number };
    specialist: { amount: number };
  } | null;
  amountSaved: number;
  loading: boolean;
}) {
  if (loading) {
    return (
      <View className="mt-3 flex-row gap-3">
        <SkeletonTile className="flex-1 h-20" />
        <SkeletonTile className="flex-1 h-20" />
        <SkeletonTile className="flex-1 h-20" />
        <SkeletonTile className="flex-1 h-20" />
      </View>
    );
  }
  return (
    <View className="mt-3 flex-row flex-wrap gap-3">
      <CopayTile
        Icon={Home}
        iconBgClass="bg-teal-soft"
        iconColor="#1F4E4A"
        label="Copay — PCP Visit"
        amount={copays?.pcp_visit.amount ?? null}
      />
      <CopayTile
        Icon={Plus}
        iconBgClass="bg-rose-soft"
        iconColor="#C75252"
        label="Copay — ER Visit"
        amount={copays?.er_visit.amount ?? null}
      />
      <CopayTile
        Icon={UserIcon}
        iconBgClass="bg-navy-soft"
        iconColor="#FFFFFF"
        label="Copay — Specialist"
        amount={copays?.specialist.amount ?? null}
      />
      <AmountSavedCard amount={amountSaved} />
    </View>
  );
}

function CopayTile({
  Icon,
  iconBgClass,
  iconColor,
  label,
  amount,
}: {
  Icon: any;
  iconBgClass: string;
  iconColor: string;
  label: string;
  amount: number | null;
}) {
  return (
    <View className="min-w-[160px] flex-1 rounded-xl bg-white p-4">
      <View className="flex-row items-center gap-3">
        <View className={`h-9 w-9 items-center justify-center rounded-md ${iconBgClass}`}>
          <Icon size={18} color={iconColor} />
        </View>
        <View className="flex-1">
          <Text className="text-[11px] font-medium text-ink/60">{label}</Text>
          <Text className="text-lg font-bold text-ink">
            {amount === null ? '—' : formatUSD(amount)}
          </Text>
        </View>
      </View>
    </View>
  );
}

function AmountSavedCard({ amount }: { amount: number }) {
  return (
    <View className="min-w-[160px] flex-1 rounded-xl bg-sage-tint p-4">
      <View className="flex-row items-center gap-3">
        <View className="h-9 w-9 items-center justify-center rounded-md bg-sage-soft">
          <CheckCircle2 size={18} color="#2E8862" />
        </View>
        <View className="flex-1">
          <Text className="text-[11px] font-medium text-ink/60">Amount Saved This Year</Text>
          <Text className="text-lg font-bold text-sage-deep">{formatUSD(amount)}</Text>
        </View>
      </View>
    </View>
  );
}

// ─── Quick Actions ─────────────────────────────────────────────────────────
function QuickActionTile({
  title,
  subtitle,
  Icon,
  onPress,
}: {
  title: string;
  subtitle: string;
  Icon: any;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className="min-w-[260px] flex-1 rounded-2xl border border-white/10 bg-navy-soft p-5"
    >
      <View className="h-9 w-9 items-center justify-center rounded-md bg-white/10">
        <Icon size={18} color="#ffffff" />
      </View>
      <Text className="mt-4 text-base font-bold text-white">{title}</Text>
      <Text className="mt-1 text-xs leading-5 text-white/55">{subtitle}</Text>
    </Pressable>
  );
}

// ─── Chat CTA ──────────────────────────────────────────────────────────────
function ChatCTA({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="mt-6 flex-row items-center gap-4 rounded-2xl bg-teal-deep p-5"
    >
      <View className="h-10 w-10 items-center justify-center rounded-md bg-white/10">
        <MessageSquare size={20} color="#ffffff" />
      </View>
      <View className="flex-1">
        <Text className="text-base font-bold text-white">Chat with AI Assistant</Text>
        <Text className="text-xs text-white/70">
          Ask anything about your health, coverage, or care options
        </Text>
      </View>
      <View className="flex-row items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1">
        <View className="h-1.5 w-1.5 rounded-full bg-sage" />
        <Text className="text-[10px] font-semibold text-white/80">Available now</Text>
      </View>
    </Pressable>
  );
}

// ─── Skeleton ──────────────────────────────────────────────────────────────
function SkeletonTile({ className }: { className?: string }) {
  return (
    <View className={`rounded-xl bg-white/5 ${className ?? ''}`} >
      <ActivityIndicator
        color="rgba(255,255,255,0.35)"
        style={{ flex: 1 }}
      />
    </View>
  );
}
