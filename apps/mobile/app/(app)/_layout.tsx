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
import { Redirect, Stack } from 'expo-router';

import { getDashboard, getProfileState } from '../../lib/api-client';
import { useCurrentUser } from '../../lib/auth';
import { isIntakeDeferred } from '../../lib/intake-deferred';

type IntakeGate = { status: string; step: string | null };

export default function AppLayout() {
  const { user, loading } = useCurrentUser();
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
        .then((d) => ({ status: d.intake_status, step: d.intake_current_step }))
        .catch(() => ({ status: 'complete', step: null }) as IntakeGate),
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
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#fff" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/sign-in" />;
  }

  // CO-17: the profile-onboarding gate runs before the coverage-intake gate.
  if (profileDone === false) {
    return <Redirect href="/onboarding" />;
  }

  // "Save & exit" sets a session-scoped deferred flag: mid-intake users may
  // reach the dashboard, but brand-new (not_started) users are always routed
  // into the wizard — they'd only see an empty dashboard otherwise.
  const intakeDeferred = intake?.status === 'in_progress' && isIntakeDeferred();

  if (intake && intake.status !== 'complete' && !intakeDeferred) {
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
        contentStyle: { backgroundColor: '#091621' },
      }}
    />
  );
}
