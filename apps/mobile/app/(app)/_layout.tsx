/**
 * Authenticated-group layout + route guard (Phase 2K) + intake gate (Phase CO-1A).
 *
 * Loads the session via useCurrentUser. While loading, shows a spinner. No user →
 * redirect to sign-in. Then checks intake_status (from /v1/dashboard): a user whose
 * intake isn't 'complete' is routed into the wizard (resuming at their current step);
 * 'complete' users fall through to the dashboard as before. The /intake/* routes live
 * OUTSIDE this (app) group, so the redirect leaves this layout — no redirect loop.
 */

import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Redirect, Stack, usePathname } from 'expo-router';

import { getDashboard, getProfileState } from '../../lib/api-client';
import { useCurrentUser } from '../../lib/auth';
import { isIntakeDeferred } from '../../lib/intake-deferred';
import { isCaseWorkRoute, shouldRedirectToWizard } from '../../lib/intake-gate';
import { themeColors } from '../../theme/useThemeColors';

type IntakeGate = { status: string; step: string | null; hasCases: boolean };

export default function AppLayout() {
  const { user, loading } = useCurrentUser();
  const pathname = usePathname();
  const [intake, setIntake] = useState<IntakeGate | null>(null);
  const [profileDone, setProfileDone] = useState<boolean | null>(null);
  const [intakeLoading, setIntakeLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setIntakeLoading(false);
      return;
    }
    let alive = true;
    // Fail open (don't trap the user) if either check errors.
    Promise.all([
      getProfileState()
        .then((p) => p.profile_completed)
        .catch(() => true),
      getDashboard()
        .then((d) => ({
          status: d.intake_status,
          step: d.intake_current_step,
          hasCases: d.has_cases,
        }))
        .catch(() => ({ status: 'complete', step: null, hasCases: true }) as IntakeGate),
    ])
      .then(([pdone, ig]) => {
        if (!alive) return;
        setProfileDone(pdone);
        setIntake(ig);
      })
      .finally(() => alive && setIntakeLoading(false));
    return () => {
      alive = false;
    };
  }, [user]);

  if (loading || (user && intakeLoading)) {
    return (
      <View className="flex-1 items-center justify-center bg-page">
        <ActivityIndicator color="var(--c-text-primary)" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/sign-in" />;
  }

  // CO-17: the profile-onboarding gate runs before the coverage-intake gate. Case-work routes
  // (/audit, /record, /case) are exempt for the same reason the intake gate exempts them — a
  // deep link to a running audit, the Record, or a sub-case must render, never bounce an existing
  // user into onboarding (the 2026-07-06 re-gating class, extended to D5's Record + sub-case).
  if (profileDone === false && !isCaseWorkRoute(pathname)) {
    return <Redirect href="/onboarding" />;
  }

  // The wizard is mandatory ONLY for brand-new users (see shouldRedirectToWizard): anyone
  // with a case file or a completed intake reaches the dashboard and is never hard-redirected
  // — "Save & exit" always exits — and /audit/* always renders (2026-07-06 fix).
  if (
    intake &&
    shouldRedirectToWizard({
      intakeStatus: intake.status,
      hasCases: intake.hasCases,
      deferred: isIntakeDeferred(),
      pathname,
    })
  ) {
    const target =
      intake.step && intake.step !== 'welcome' && intake.step !== 'complete'
        ? `/intake/${intake.step}`
        : '/intake/welcome';
    return <Redirect href={target as never} />;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: themeColors('dark').bg.page },
      }}
    />
  );
}
