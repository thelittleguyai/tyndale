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

import { getDashboard } from '../../lib/api-client';
import { useCurrentUser } from '../../lib/auth';

type IntakeGate = { status: string; step: string | null };

export default function AppLayout() {
  const { user, loading } = useCurrentUser();
  const [intake, setIntake] = useState<IntakeGate | null>(null);
  const [intakeLoading, setIntakeLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      setIntakeLoading(false);
      return;
    }
    let alive = true;
    getDashboard()
      .then((d) => alive && setIntake({ status: d.intake_status, step: d.intake_current_step }))
      // Fail open to the dashboard rather than trapping the user if the check errors.
      .catch(() => alive && setIntake({ status: 'complete', step: null }))
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

  if (intake && intake.status !== 'complete') {
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
