/**
 * Intake wizard layout (Phase CO-1A). Plain stack; each step renders its own
 * chrome (progress bar + Save & exit) via WizardShell. /intake/* lives OUTSIDE the
 * (app) group, so it needs its own auth guard (Phase 3.4) — an unauthenticated visitor
 * is bounced to sign-in instead of hitting a 401 that surfaces as "check your connection".
 */

import { ActivityIndicator, View } from 'react-native';
import { Redirect, Stack } from 'expo-router';

import { useCurrentUser } from '../../lib/auth';

export default function IntakeLayout() {
  const { user, loading } = useCurrentUser();
  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#5eead4" />
      </View>
    );
  }
  if (!user) return <Redirect href="/sign-in" />;
  return (
    <Stack
      screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#091621' } }}
    />
  );
}
