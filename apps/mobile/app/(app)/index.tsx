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
  CheckCircle2,
  Clock,
  FileText,
  MessageSquare,
  Plus,
  Settings,
  ShieldCheck,
} from 'lucide-react-native';

import {
  createConversation,
  getDashboard,
  getSurfaceCopy,
  recordCallOutcome,
  type SurfaceCopy,
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
import { RecordSection } from '../../components/record/RecordSection';
import { CaseRemoveButton, isCaseRemovable } from '../../components/record/CaseRemoveButton';
import { PressableScale } from '../../components/ui/PressableScale';
import { ScreenView } from '../../components/ui/Screen';
import { useBreakpoint } from '../../components/ui/use-breakpoint';
import { MetricCard } from '../../components/ui';
import type { SemanticColors } from '../../theme/tokens';
import { useThemeColors } from '../../theme/useThemeColors';

const formatUSD = (n: number) =>
  '$' + n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function DashboardScreen() {
  const tc = useThemeColors();
  const router = useRouter();
  const { width } = useBreakpoint();
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
  const [homeCopy, setHomeCopy] = useState<SurfaceCopy>({});

  useEffect(() => {
    getSurfaceCopy('home').then(setHomeCopy).catch(() => setHomeCopy({}));
  }, []);

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
    <View className="flex-1 bg-page">
    <ScrollView
      className="flex-1 bg-page"
      contentContainerStyle={{ paddingBottom: 96 }}
    >
      <Header />

      <ScreenView wide className="px-5 pt-3">
        {/* Welcome banner (mockup item 2) — registry copy whose subline states only REAL
            computed case state; the mockup's proactive-monitoring line is B8, unbuilt. */}
        <View className="mb-5 mt-1">
          <Text className="text-title text-primary" testID="banner-title">
            {data?.banner?.title ?? `Welcome back, ${greetingName}.`}
          </Text>
          <Text className="mt-1 text-body text-secondary" testID="banner-subline">
            {data?.banner?.subline ??
              (loading && !data ? 'Loading your dashboard…' : 'What would you like to do today?')}
          </Text>
        </View>

        {data?.intake_status === 'in_progress' ? (
          <FinishSetupCard currentStep={data.intake_current_step} />
        ) : null}

        {/* B5 (round-2) — the check-in leads the screen: "how did the call go?" is the first
            thing a returning user with an open loop sees, above the metrics. The advocate asks
            about YOUR fight before showing its dashboards. */}
        {(data?.outcome_prompts ?? []).length > 0 ? (
          <OutcomeFollowupCard prompt={data!.outcome_prompts[0]} copy={homeCopy} onDone={load} />
        ) : null}

        {/* Stat cards (mockup item 3): CONFIRMED recovered only — a neutral empty state
            when nothing is confirmed yet, never $0.00 as a sad zero — and open cases with
            the needs-you count. */}
        <StatCards
          recovered={data?.recovered_to_date ?? 0}
          openCount={data?.open_count ?? 0}
          needsYou={data?.needs_you_count ?? 0}
          loading={loading && !data}
        />

        {/* Quick actions (mockup item 6) — BUILT features only. The mockup's Estimate
            Costs / Find a Doctor / Plan a Visit are §5 expanded-scope, not started: dead
            buttons are worse than absent ones, so they are gone, not "coming soon". */}
        <Text className="mb-3 mt-6 text-xs text-faint">
          Quick actions
        </Text>
        <View className="flex-row flex-wrap gap-3">
          <QuickActionTile
            title="Check a bill"
            subtitle="Upload a bill or EOB and I'll audit every charge."
            Icon={FileText}
            onPress={() => router.push('/upload')}
          />
          <QuickActionTile
            title="Chat with Tyndale"
            subtitle="Ask anything about a bill, a denial, or your coverage."
            Icon={MessageSquare}
            onPress={openChat}
          />
          {data?.coverage_connection_enabled ? (
            <QuickActionTile
              title="Connect your plan"
              subtitle="Link your insurance so audits use your real coverage terms."
              Icon={ShieldCheck}
              onPress={() => router.push('/settings')}
            />
          ) : null}
        </View>

        {/* Benefit bars (mockup, conditional): ONLY real attested/extracted values — a
            missing meter renders nothing (never a bar from a prior), and each bar names
            its source honestly. */}
        <BenefitBars coverage={data?.coverage ?? null} />

        {/* Your record — below Quick Actions + chat banner per the 2026-07-15 review. */}
        {data?.record_enabled ? (
          record ? <RecordSection record={record} onChanged={load} /> : null
        ) : (data?.active_cases ?? []).length > 0 ? (
          <ActiveCasesSection cases={data!.active_cases} onChanged={load} />
        ) : null}


        {error ? (
          <View className="mt-4 rounded-2xl border border-hairline bg-surface p-5" testID="dashboard-load-error">
            <Text className="text-body leading-6 text-secondary">
              Something went wrong loading your dashboard. Your cases are safe — try again.
            </Text>
            <PressableScale
              onPress={() => void load()}
              className="mt-3 min-h-[44px] items-center justify-center self-start rounded-xl bg-accent px-4"
              testID="dashboard-retry"
            >
              <Text className="text-body font-bold text-on-accent">Try again</Text>
            </PressableScale>
          </View>
        ) : null}

        <Text className="mt-10 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </ScreenView>
    </ScrollView>
    {/* Persistent chat entry (mockup item 1): floats above the scroll, routes to freeform. */}
    {/* <480 the pill compacts to an icon bubble: the labeled quick-action card is right
        there, and the full pill overlays content at phone widths (viewport sweep note). */}
    <PressableScale
      onPress={openChat}
      accessibilityRole="button"
      accessibilityLabel="Chat with Tyndale"
      className={`absolute bottom-6 right-5 flex-row items-center justify-center rounded-full bg-accent shadow-card ${
        width < 480 ? 'h-[52px] w-[52px]' : 'min-h-[52px] gap-2 px-5 py-3'
      }`}
      testID="floating-chat"
    >
      <MessageSquare size={18} color={tc.onAccent} />
      {width < 480 ? null : (
        <Text className="text-body font-bold text-on-accent">Chat with Tyndale</Text>
      )}
    </PressableScale>
    </View>
  );
}

// ─── Outcome follow-up (Phase 2J · mockup item 5) ────────────────────────────
// The three route chips are CALL ROUTES, not outcomes (H6 doctrine): a tap records the route
// and defers the real "did it get resolved?" by the follow-up window — never retires it.
// "Yes, resolved" and "Skip for now" remain the outcome_report path.
const CHECKIN_FALLBACK = {
  fixing_it: "They're fixing it",
  pushed_back: 'They pushed back',
  left_message: 'I left a message',
} as const;

function OutcomeFollowupCard({
  prompt,
  copy = {},
  onDone,
}: {
  prompt: { case_file_id: string; days_since_recommendation: number; finding_summary: string };
  copy?: SurfaceCopy;
  onDone: () => void;
}) {
  const tc = useThemeColors();
  const [submitting, setSubmitting] = useState(false);
  const [remind, setRemind] = useState(false);

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

  const route = async (r: 'fixing_it' | 'pushed_back' | 'left_message') => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // Records the route + stamps the recency clock (defers, never resolves — H6).
      await recordCallOutcome(prompt.case_file_id, 'dashboard-checkin', r);
      onDone();
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <View className="mt-6 rounded-2xl border border-warning bg-surface p-5 shadow-card" testID="checkin-card">
      <View className="mb-2 flex-row items-center gap-3">
        <View className="h-9 w-9 items-center justify-center rounded-md bg-warning-tint">
          <Clock size={18} color={tc.warning.base} />
        </View>
        <Text className="text-base font-bold text-primary">Quick check-in: how did it go?</Text>
      </View>
      <View className="flex-row flex-wrap gap-2">
        <OutcomeButton label="Yes, resolved" tone="sage" onPress={() => answer('yes')} />
        <OutcomeButton
          label={copy.checkin_fixing_it || CHECKIN_FALLBACK.fixing_it}
          tone="amber"
          onPress={() => route('fixing_it')}
        />
        <OutcomeButton
          label={copy.checkin_pushed_back || CHECKIN_FALLBACK.pushed_back}
          tone="rose"
          onPress={() => route('pushed_back')}
        />
        <OutcomeButton
          label={copy.checkin_left_message || CHECKIN_FALLBACK.left_message}
          tone="ink"
          onPress={() => route('left_message')}
        />
        <OutcomeButton label="Skip for now" tone="ink" onPress={() => answer('pending')} />
      </View>
      <Pressable
        onPress={() => setRemind((r) => !r)}
        className="mt-3 min-h-[44px] justify-center self-start"
        testID="checkin-remind"
      >
        <Text className="text-caption text-secondary underline">Remind me what this was about</Text>
      </Pressable>
      {remind ? (
        <Text className="text-body leading-6 text-secondary" testID="checkin-context">
          {prompt.days_since_recommendation} days ago I helped you with {prompt.finding_summary}.
        </Text>
      ) : null}
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
      ? 'bg-accent'
      : tone === 'amber'
        ? 'bg-warning'
        : tone === 'rose'
          ? 'bg-danger'
          : 'bg-inset';
  const textCls = tone === 'ink' ? 'text-secondary' : 'text-on-accent';
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
  const tc = useThemeColors();
  const router = useRouter();
  const target =
    currentStep && currentStep !== 'welcome' && currentStep !== 'complete'
      ? `/intake/${currentStep}`
      : '/intake/welcome';
  return (
    <View className="mt-4 flex-row items-center gap-4 rounded-2xl border border-hairline bg-surface p-4 shadow-card">
      <View className="h-9 w-9 items-center justify-center rounded-md bg-accent-tint">
        <CheckCircle2 size={18} color={tc.accent} />
      </View>
      <View className="flex-1">
        <Text className="text-body font-bold text-primary">Finish setting up</Text>
        <Text className="mt-0.5 text-xs leading-5 text-secondary">
          Your intake is saved where you left off — a few more steps unlock your full
          dashboard.
        </Text>
      </View>
      <PressableScale
        onPress={() => router.push(target as never)}
        className="min-h-[44px] items-center justify-center rounded-lg bg-accent px-3 py-2 hover:bg-accent"
      >
        <Text className="text-xs font-bold text-on-accent">Resume</Text>
      </PressableScale>
    </View>
  );
}

// ─── Open cases (status-aware, full lifecycle) ───────────────────────────────
// Maps a case status to its card icon/color so a glance tells the user where each case stands:
// results ready (sage), running/starting (amber), needs attention (rose), otherwise neutral.
function statusVisual(
  status: string,
  tc: SemanticColors,
): { Icon: typeof FileText; color: string; bg: string } {
  switch (status) {
    case 'audit_complete':
      return { Icon: CheckCircle2, color: tc.success.base, bg: 'bg-accent-tint' };
    case 'audit_running':
    case 'encounter_verified':
      return { Icon: Clock, color: tc.warning.base, bg: 'bg-warning-tint' };
    case 'extraction_failed':
    case 'audit_incomplete':
      return { Icon: AlertCircle, color: tc.danger.base, bg: 'bg-danger-tint' };
    default:
      return { Icon: FileText, color: tc.text.primary, bg: 'bg-inset' };
  }
}


function ActiveCasesSection({
  cases,
  onChanged,
}: {
  cases: ActiveCase[];
  onChanged: () => void;
}) {
  const router = useRouter();
  const tc = useThemeColors();
  return (
    <View>
      <Text className="mb-3 mt-6 text-xs text-faint">
        Open Cases
      </Text>
      <View className="gap-3">
        {cases.map((c) => {
          const { Icon, color, bg } = statusVisual(c.status, tc);
          return (
            <PressableScale
              key={c.case_file_id}
              onPress={() => router.push(activeCaseRoute(c) as never)}
              accessibilityRole="button"
              accessibilityLabel={`${c.label} — open case`}
              className="flex-row items-center gap-4 rounded-2xl border border-hairline bg-surface p-5 shadow-card hover:border-hairline"
            >
              <View className={`h-9 w-9 items-center justify-center rounded-md ${bg}`}>
                <Icon size={18} color={color} />
              </View>
              <View className="flex-1">
                <Text className="text-base font-bold text-primary">{c.label}</Text>
                <Text className="mt-1 text-xs text-faint">
                  {c.days_open === 0
                    ? 'Opened today'
                    : `Open for ${c.days_open} day${c.days_open === 1 ? '' : 's'}`}
                  {c.next_deadline_label && c.next_deadline_date
                    ? ` · ${c.next_deadline_label}: ${c.next_deadline_date}`
                    : ''}
                </Text>
              </View>
              <Text className="text-sm text-faint">›</Text>
              {isCaseRemovable(c.status) ? (
                <CaseRemoveButton caseId={c.case_file_id} label={c.label} onDone={onChanged} />
              ) : null}
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

function Header() {
  const tc = useThemeColors();
  const router = useRouter();
  const signOut = useSignOut();
  // Phones (<640): logo-only. Narrow (<480, down to 320): Sign Out and the Admin chip
  // collapse into Settings (both exist there), and the primary compacts to '+ Check' —
  // nothing ever clips (2026-08-26 viewport sweep).
  const { isPhone, width } = useBreakpoint();
  const narrow = width < 480;
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
    <View className="flex-row items-center justify-between bg-surface px-5 py-3">
      <View className="flex-row items-center gap-2">
        <SvgXml xml={logoSvg} width={28} height={28} />
        {isPhone ? null : <Text className="text-base font-bold text-primary">Tyndale</Text>}
      </View>
      <View className="flex-row items-center gap-2">
        {isAdmin && !narrow ? (
          <Pressable
            onPress={() => {
              Linking.openURL(ADMIN_CONSOLE_URL).catch(() => {});
            }}
            accessibilityRole="button"
            accessibilityHint="Opens the Tyndale admin console in a new tab"
            className="min-h-[44px] flex-row items-center gap-1.5 rounded-full border border-hairline bg-inset px-3 py-1.5 hover:bg-inset active:opacity-80"
          >
            <ShieldCheck size={14} color={tc.text.secondary} />
            <Text className="text-xs font-semibold text-secondary">Admin</Text>
          </Pressable>
        ) : null}
        <PressableScale
          onPress={() => router.push('/upload')}
          accessibilityRole="button"
          accessibilityLabel="Check a bill"
          className="min-h-[44px] flex-row items-center gap-1 rounded-full bg-accent px-3.5 py-1.5"
          testID="header-check-bill"
        >
          <Plus size={14} color={tc.onAccent} />
          <Text className="text-xs font-bold text-on-accent">{narrow ? 'Check' : 'Check a bill'}</Text>
        </PressableScale>
        <Pressable
          onPress={() => router.push('/settings')}
          accessibilityRole="button"
          accessibilityLabel="Settings"
          className="min-h-[44px] min-w-[44px] items-center justify-center rounded-full border border-hairline bg-inset hover:bg-inset active:opacity-80"
          testID="header-settings"
        >
          <Settings size={17} color={tc.text.secondary} />
        </Pressable>
        {narrow ? null : (
          <Pressable
            onPress={onSignOut}
            disabled={signingOut}
            className="min-h-[44px] items-center justify-center rounded-full bg-inset px-3 py-1.5 hover:bg-inset active:opacity-80"
          >
            <Text className="text-xs font-semibold text-secondary">
              {signingOut ? 'Signing out…' : 'Sign out'}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

// ─── Stat cards (mockup item 3) ─────────────────────────────────────────────
// Recovered = CONFIRMED outcome money only; a neutral empty state below $1 (never a sad
// $0.00). Open cases carries the needs-you count from the server's user-actionable set.
function StatCards({
  recovered,
  openCount,
  needsYou,
  loading,
}: {
  recovered: number;
  openCount: number;
  needsYou: number;
  loading: boolean;
}) {
  // <400 the two-up grid squeezes the empty-state copy into awkward wraps — stack.
  const { width } = useBreakpoint();
  const stack = width < 400;
  if (loading) {
    return (
      <View className="mb-2 flex-row flex-wrap gap-3">
        {[0, 1].map((i) => (
          <SkeletonTile key={i} className="h-24 min-w-[150px] flex-1" />
        ))}
      </View>
    );
  }
  return (
    <View className={`mb-2 gap-3 ${stack ? '' : 'flex-row flex-wrap'}`}>
      <View className="min-w-[150px] flex-1" testID="stat-recovered">
        {recovered > 0 ? (
          <MetricCard
            label="Recovered to date"
            value={formatUSD(recovered)}
            qualifier="confirmed"
            valueTone="accent"
          />
        ) : (
          <MetricCard
            label="Recovered to date"
            value="—"
            qualifier="your confirmed wins land here"
          />
        )}
      </View>
      <View className="min-w-[150px] flex-1" testID="stat-open-cases">
        <MetricCard
          label="Open cases"
          value={String(openCount)}
          qualifier={
            needsYou > 0
              ? `${needsYou} need${needsYou === 1 ? 's' : ''} you`
              : openCount > 0
                ? 'all moving'
                : 'none yet'
          }
          valueTone={needsYou > 0 ? 'warning' : undefined}
        />
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
  const tc = useThemeColors();
  const { isPhone } = useBreakpoint();
  return (
    <PressableScale
      onPress={onPress}
      className={`relative rounded-2xl border border-hairline bg-surface p-5 shadow-card hover:border-hairline ${
        isPhone ? 'w-full' : 'min-w-[260px] flex-1'
      }`}
    >
      <View className="h-9 w-9 items-center justify-center rounded-md bg-inset">
        <Icon size={18} color={tc.text.primary} />
      </View>
      <Text className="mt-4 text-base font-bold text-primary">{title}</Text>
      <Text className="mt-1 text-xs leading-5 text-faint">{subtitle}</Text>
    </PressableScale>
  );
}

// ─── Benefit bars (mockup, honest conditional) ─────────────────────────────
function BenefitBars({ coverage }: { coverage: DashboardPayload['coverage'] | null }) {
  const sourceLabel = (s?: string | null) =>
    s === 'entries' ? 'from your entries' : 'from your SBC';
  const bars = [
    coverage?.deductible
      ? { key: 'deductible', label: 'Deductible', meter: coverage.deductible, source: coverage.deductible_source, tone: 'success' as const }
      : null,
    coverage?.oop_max
      ? { key: 'oop', label: 'Out-of-pocket max', meter: coverage.oop_max, source: coverage.oop_max_source, tone: 'warning' as const }
      : null,
  ].filter(Boolean) as {
    key: string;
    label: string;
    meter: { total: number; met: number };
    source?: string | null;
    tone: 'success' | 'warning';
  }[];
  if (bars.length === 0) return null;
  const pct = (m: { total: number; met: number }) =>
    m.total > 0 ? Math.max(0, Math.min(1, m.met / m.total)) : 0;
  return (
    <View className="mt-6 flex-row flex-wrap gap-3" testID="benefit-bars">
      {bars.map((b) => (
        <View key={b.key} className="min-w-[150px] flex-1">
          <MetricCard
            label={b.label}
            value={formatUSD(b.meter.met)}
            sub={` / ${formatUSD(b.meter.total)}`}
            progress={pct(b.meter)}
            tone={b.tone}
            qualifier={sourceLabel(b.source)}
          />
        </View>
      ))}
    </View>
  );
}

// ─── Skeleton ──────────────────────────────────────────────────────────────
function SkeletonTile({ className }: { className?: string }) {
  const tc = useThemeColors();
  return (
    <View className={`rounded-xl bg-inset ${className ?? ''}`} >
      <ActivityIndicator
        color={tc.text.faint}
        style={{ flex: 1 }}
      />
    </View>
  );
}
