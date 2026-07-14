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
  Alert,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SvgXml } from 'react-native-svg';
import {
  AlertCircle,
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
  X,
} from 'lucide-react-native';

import {
  createConversation,
  getDashboard,
  getRecord,
  getProfileState,
  getUserProfile,
  listConversations,
  makeFeedbackEvent,
  removeCase,
  submitFeedback,
  type DashboardPayload,
  type RecordPayload,
  type ResolvedValue,
} from '../../lib/api-client';
import { useSignOut } from '../../lib/auth';
import { clearIntakeDeferred } from '../../lib/intake-deferred';
import { logoSvg, type ActiveCase } from '@tyndale/shared';
import { activeCaseRoute } from '../../lib/active-cases';
import { HeroMotif } from '../../components/hero-motif';
import { RecordSection } from '../../components/record/RecordSection';
import { PressableScale } from '../../components/ui/PressableScale';
import { ScreenView } from '../../components/ui/Screen';
import { useBreakpoint } from '../../components/ui/use-breakpoint';

const formatUSD = (n: number) =>
  '$' + n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function DashboardScreen() {
  const router = useRouter();
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [record, setRecord] = useState<RecordPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // CO-17: the profile record carries the real first/last name (both nullable).
  // The dashboard payload's user.first_name is derived from the email local-part
  // (e.g. "pfluegelcx"), so prefer the real profile name for the greeting +
  // header pill and fall back to the derived value only when it's empty. One
  // fetch here feeds both the Hero greeting and the Header pill (no double-fetch).
  const [profileName, setProfileName] = useState<{ first: string | null; last: string | null }>({
    first: null,
    last: null,
  });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const d = await getDashboard();
      setData(d);
      if (d.record_enabled) {
        getRecord()
          .then(setRecord)
          .catch(() => setRecord(null));
      }
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getProfileState()
      .then((s) =>
        setProfileName({ first: s.first_name?.trim() || null, last: s.last_name?.trim() || null }),
      )
      .catch(() => setProfileName({ first: null, last: null }));
  }, []);

  // "Chat with AI Assistant" opens a thread directly: resume the most recent
  // freeform conversation, or create one — skipping the conversation-list page.
  const openChat = useCallback(async () => {
    try {
      const list = await listConversations({ mode: 'freeform', limit: 1 });
      const existing = list.conversations[0];
      const id = existing
        ? existing.conversation_id
        : (await createConversation()).conversation_id;
      router.push(`/chat/${id}`);
    } catch {
      router.push('/chat');
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  // Real first name from the profile wins; fall back to the dashboard's
  // email-derived value only when the profile name is empty.
  const greetingName = profileName.first ?? data?.user.first_name ?? 'there';

  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Header firstName={greetingName} lastName={profileName.last} />

      <ScreenView wide className="px-5 pt-3">
        <Hero
          firstName={greetingName}
          statusGreeting={data?.status_forward_greeting ?? null}
          loading={loading && !data}
        />

        {data?.intake_status === 'in_progress' ? (
          <FinishSetupCard currentStep={data.intake_current_step} />
        ) : null}

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

        {data?.record_enabled ? (
          record ? <RecordSection record={record} /> : null
        ) : (data?.active_cases ?? []).length > 0 ? (
          <ActiveCasesSection cases={data!.active_cases} onChanged={load} />
        ) : null}

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
            comingSoon
            onPress={() => router.push('/plan-a-visit-placeholder')}
          />
          <QuickActionTile
            title="Find a Doctor"
            subtitle="Search in-network providers and specialists near you."
            Icon={Search}
            comingSoon
            onPress={() => router.push('/find-a-doctor-placeholder')}
          />
          <QuickActionTile
            title="Estimate Costs"
            subtitle="Get transparent pricing and coverage estimates before care."
            Icon={Clock}
            comingSoon
            onPress={() => router.push('/estimate-costs-placeholder')}
          />
        </View>

        {(data?.outcome_prompts ?? []).length > 0 ? (
          <OutcomeFollowupCard prompt={data!.outcome_prompts[0]} onDone={load} />
        ) : null}

        <ChatCTA onPress={openChat} />

        {error ? (
          <Text className="mt-4 text-xs text-rose">Dashboard fetch error: {error}</Text>
        ) : null}

        <Text className="mt-10 text-center text-xs text-white/40">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </ScreenView>
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
    <View className="mt-6 rounded-2xl border border-amber/30 bg-navy-soft p-5 shadow-card">
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
    <PressableScale
      onPress={onPress}
      className={`min-h-[44px] items-center justify-center rounded-lg px-3 py-2 ${cls}`}
    >
      <Text className={`text-xs font-bold ${textCls}`}>{label}</Text>
    </PressableScale>
  );
}

// ─── Finish-setup resume card (Save & exit follow-up) ───────────────────────
// Shown when the user deferred intake mid-wizard: a gentle path back in.
function FinishSetupCard({ currentStep }: { currentStep: string | null }) {
  const router = useRouter();
  const target =
    currentStep && currentStep !== 'welcome' && currentStep !== 'complete'
      ? `/intake/${currentStep}`
      : '/intake/welcome';
  return (
    <View className="mt-4 flex-row items-center gap-4 rounded-2xl border border-white/10 bg-navy-soft p-4 shadow-card">
      <View className="h-9 w-9 items-center justify-center rounded-md bg-sage/20">
        <CheckCircle2 size={18} color="#3DAA7E" />
      </View>
      <View className="flex-1">
        <Text className="text-sm font-bold text-white">Finish setting up</Text>
        <Text className="mt-0.5 text-xs leading-5 text-white/60">
          Your intake is saved where you left off — a few more steps unlock your full
          dashboard.
        </Text>
      </View>
      <PressableScale
        onPress={() => router.push(target as never)}
        className="min-h-[44px] items-center justify-center rounded-lg bg-sage px-3 py-2 hover:bg-sage-deep"
      >
        <Text className="text-xs font-bold text-ink">Resume</Text>
      </PressableScale>
    </View>
  );
}

// ─── Open cases (status-aware, full lifecycle) ───────────────────────────────
// Maps a case status to its card icon/color so a glance tells the user where each case stands:
// results ready (sage), running/starting (amber), needs attention (rose), otherwise neutral.
function statusVisual(status: string): { Icon: typeof FileText; color: string; bg: string } {
  switch (status) {
    case 'audit_complete':
      return { Icon: CheckCircle2, color: '#3DAA7E', bg: 'bg-sage/20' };
    case 'audit_running':
    case 'encounter_verified':
      return { Icon: Clock, color: '#E08A3C', bg: 'bg-amber/20' };
    case 'extraction_failed':
    case 'audit_incomplete':
      return { Icon: AlertCircle, color: '#C75252', bg: 'bg-rose/20' };
    default:
      return { Icon: FileText, color: '#ffffff', bg: 'bg-white/10' };
  }
}

// A case is user-removable unless it carries a real result (in-flight or complete audit); the
// server is authoritative (409) and also blocks any case that produced findings.
const NON_REMOVABLE_STATUSES = new Set(['audit_running', 'audit_complete', 'resolved']);

function confirmRemoveCase(label: string): Promise<boolean> {
  const msg = `Remove “${label}”? This clears it from your dashboard.`;
  if (Platform.OS === 'web') {
    return Promise.resolve(typeof window !== 'undefined' ? window.confirm(msg) : true);
  }
  return new Promise((resolve) => {
    Alert.alert('Remove case', msg, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: 'Remove', style: 'destructive', onPress: () => resolve(true) },
    ]);
  });
}

function CaseRemoveButton({
  caseId,
  label,
  onDone,
}: {
  caseId: string;
  label: string;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const onPress = async (e?: any) => {
    e?.stopPropagation?.(); // don't also open the case (web bubbling; native captures the child)
    if (busy) return;
    if (!(await confirmRemoveCase(label))) return;
    setBusy(true);
    try {
      await removeCase(caseId);
      onDone();
    } catch {
      setBusy(false);
      const m = "We couldn't remove that case — it may have results.";
      if (Platform.OS === 'web' && typeof window !== 'undefined') window.alert(m);
      else Alert.alert('Could not remove', m);
    }
  };
  return (
    <Pressable
      onPress={onPress}
      hitSlop={10}
      accessibilityRole="button"
      accessibilityLabel={`Remove ${label}`}
      className="ml-1 rounded-full p-1.5 hover:bg-white/10"
    >
      {busy ? (
        <ActivityIndicator size="small" color="#ffffff99" />
      ) : (
        <X size={16} color="#ffffff70" />
      )}
    </Pressable>
  );
}

function ActiveCasesSection({
  cases,
  onChanged,
}: {
  cases: ActiveCase[];
  onChanged: () => void;
}) {
  const router = useRouter();
  return (
    <View>
      <Text className="mb-3 mt-6 text-xs uppercase tracking-widest text-white/45">
        Open Cases
      </Text>
      <View className="gap-3">
        {cases.map((c) => {
          const { Icon, color, bg } = statusVisual(c.status);
          return (
            <PressableScale
              key={c.case_file_id}
              onPress={() => router.push(activeCaseRoute(c) as never)}
              accessibilityRole="button"
              accessibilityLabel={`${c.label} — open case`}
              className="flex-row items-center gap-4 rounded-2xl border border-white/10 bg-navy-soft p-5 shadow-card hover:border-white/25"
            >
              <View className={`h-9 w-9 items-center justify-center rounded-md ${bg}`}>
                <Icon size={18} color={color} />
              </View>
              <View className="flex-1">
                <Text className="text-base font-bold text-white">{c.label}</Text>
                <Text className="mt-1 text-xs text-white/55">
                  {c.days_open === 0
                    ? 'Opened today'
                    : `Open for ${c.days_open} day${c.days_open === 1 ? '' : 's'}`}
                  {c.next_deadline_label && c.next_deadline_date
                    ? ` · ${c.next_deadline_label}: ${c.next_deadline_date}`
                    : ''}
                </Text>
              </View>
              <Text className="text-sm text-white/30">›</Text>
              {NON_REMOVABLE_STATUSES.has(c.status) ? null : (
                <CaseRemoveButton caseId={c.case_file_id} label={c.label} onDone={onChanged} />
              )}
            </PressableScale>
          );
        })}
      </View>
    </View>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────────
// The separate admin console (CO-9) lives at its own IP-allowlisted subdomain.
const ADMIN_CONSOLE_URL = 'https://admin.tyndaleapp.net';

function Header({ firstName, lastName }: { firstName: string; lastName: string | null }) {
  const router = useRouter();
  const signOut = useSignOut();
  const [isAdmin, setIsAdmin] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const onSignOut = useCallback(async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await signOut(); // clears the server cookie + local token
    } catch {
      // Best effort — navigate to sign-in regardless so the user isn't stuck.
    }
    clearIntakeDeferred();
    router.replace('/sign-in');
  }, [router, signOut, signingOut]);

  // The Admin pill is admin-only: DL-60 anti-enumeration means non-admins must
  // never even see that an admin surface exists. It deep-links out to the
  // standalone console (Linking.openURL → new tab on web, system browser on
  // native). That console is IP-allowlisted, so it only loads on an allowed
  // network — the pill is a convenience jump-off, not an in-app screen.
  useEffect(() => {
    getUserProfile()
      .then((p) => setIsAdmin(p?.user_type === 'admin'))
      .catch(() => setIsAdmin(false));
    // last_name arrives via props from the dashboard's single profile fetch.
  }, []);

  return (
    <View className="flex-row items-center justify-between bg-navy-soft px-5 py-3">
      <View className="flex-row items-center gap-2">
        <SvgXml xml={logoSvg} width={28} height={28} />
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
            className="min-h-[44px] flex-row items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 hover:bg-white/10 active:opacity-80"
          >
            <ShieldCheck size={14} color="rgba(255,255,255,0.7)" />
            <Text className="text-xs font-semibold text-white/80">Admin</Text>
          </Pressable>
        ) : null}
        <Pressable
          onPress={() => router.push('/settings')}
          accessibilityRole="button"
          className="min-h-[44px] flex-row items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-2.5 py-1.5 hover:bg-white/10 active:opacity-80"
        >
          <View className="h-5 w-5 items-center justify-center rounded-full bg-amber/80">
            <Text className="text-[10px] font-bold text-ink">
              {firstName.charAt(0).toUpperCase()}
            </Text>
          </View>
          <Text className="text-xs font-medium text-white/90">
            {lastName ? `${firstName} ${lastName}` : firstName}
          </Text>
        </Pressable>
        <Pressable
          onPress={onSignOut}
          disabled={signingOut}
          className="min-h-[44px] items-center justify-center rounded-full bg-white/5 px-3 py-1.5 hover:bg-white/10 active:opacity-80"
        >
          <Text className="text-xs font-semibold text-white/80">
            {signingOut ? 'Signing out…' : 'Sign Out'}
          </Text>
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
  const { isPhone } = useBreakpoint();
  return (
    <View className="relative overflow-hidden rounded-2xl bg-teal-deep px-5 py-7">
      <View className="absolute -right-6 -top-6 opacity-80">
        <HeroMotif size={isPhone ? 116 : 170} />
      </View>
      <View className={`relative z-10 ${isPhone ? 'pr-16' : 'pr-32'}`}>
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
        <PressableScale
          onPress={onUploadPress}
          className="mt-3 self-start rounded-md bg-sage px-3 py-2 hover:bg-sage-deep"
        >
          <Text className="text-xs font-bold text-ink">Upload insurance card</Text>
        </PressableScale>
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
      <View className="flex-1 rounded-xl bg-white p-4 shadow-card">
        <Text className="text-sm font-semibold text-ink">{label}</Text>
        <Text className="mt-2 text-xs text-ink/60">Pending extraction…</Text>
      </View>
    );
  }
  const pct = Math.max(0, Math.min(1, meter.total > 0 ? meter.met / meter.total : 0));
  return (
    <View className="flex-1 rounded-xl bg-white p-4 shadow-card">
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
    <View className="min-w-[160px] flex-1 rounded-xl bg-white p-4 shadow-card">
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
    <View className="min-w-[160px] flex-1 rounded-xl bg-sage-tint p-4 shadow-card">
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
  comingSoon = false,
}: {
  title: string;
  subtitle: string;
  Icon: any;
  onPress: () => void;
  // Full-V1 placeholders (Plan a Visit / Find a Doctor / Estimate Costs) tag a
  // subtle "Coming soon" pill so users know they're not yet functional.
  comingSoon?: boolean;
}) {
  const { isPhone } = useBreakpoint();
  return (
    <PressableScale
      onPress={onPress}
      className={`relative rounded-2xl border border-white/10 bg-navy-soft p-5 shadow-card hover:border-white/25 ${
        isPhone ? 'w-full' : 'min-w-[260px] flex-1'
      }`}
    >
      {comingSoon ? (
        <View className="absolute right-3 top-3 rounded-full bg-white/10 px-2 py-0.5">
          <Text className="text-[10px] font-semibold text-white/50">Coming soon</Text>
        </View>
      ) : null}
      <View className="h-9 w-9 items-center justify-center rounded-md bg-white/10">
        <Icon size={18} color="#ffffff" />
      </View>
      <Text className="mt-4 text-base font-bold text-white">{title}</Text>
      <Text className="mt-1 text-xs leading-5 text-white/55">{subtitle}</Text>
    </PressableScale>
  );
}

// ─── Chat CTA ──────────────────────────────────────────────────────────────
function ChatCTA({ onPress }: { onPress: () => void }) {
  return (
    <PressableScale
      onPress={onPress}
      className="mt-6 flex-row items-center gap-4 rounded-2xl bg-teal-deep p-5 shadow-card hover:bg-teal"
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
    </PressableScale>
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
