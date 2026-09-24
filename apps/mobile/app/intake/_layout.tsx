/**
 * Intake wizard layout (Phase CO-1A). Plain stack; each step renders its own
 * chrome (progress bar + Save & exit) via WizardShell. /intake/* lives OUTSIDE the
 * (app) group, so it needs its own auth guard (Phase 3.4) — an unauthenticated visitor
 * is bounced to sign-in instead of hitting a 401 that surfaces as "check your connection".
 */

import { ActivityIndicator, View } from 'react-native';
import { Redirect, Stack, useGlobalSearchParams } from 'expo-router';

import { useCurrentUser } from '../../lib/auth';
import { themeColors, useThemeColors } from '../../theme/useThemeColors';

export default function IntakeLayout() {
  const tc = useThemeColors();
  const { user, loading } = useCurrentUser();
  const { case: caseId, screen } = useGlobalSearchParams<{ case?: string; screen?: string }>();
  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-page">
        <ActivityIndicator color={tc.accent} />
      </View>
    );
  }
  if (!user) {
    // the resume path (doc 40 decision 7): sign in and come straight back to THIS intake
    const q = new URLSearchParams();
    if (caseId) q.set('case', String(caseId));
    if (screen) q.set('screen', String(screen));
    const back = `/intake${q.toString() ? `?${q.toString()}` : ''}`;
    return <Redirect href={`/sign-in?return=${encodeURIComponent(back)}` as never} />;
  }
  return (
    <Stack
      screenOptions={{ headerShown: false, contentStyle: { backgroundColor: themeColors('dark').bg.page } }}
    />
  );
}
