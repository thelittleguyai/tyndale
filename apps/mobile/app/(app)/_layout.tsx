/**
 * Authenticated-group layout + route guard (Phase 2K).
 *
 * Loads the session via useCurrentUser. While loading, shows a spinner.
 * If there's no user (real auth + no/invalid cookie), redirects to sign-in.
 * Under USE_REAL_AUTH=false the runtime returns the dev admin user, so the
 * guard passes transparently in local dev.
 */

import { ActivityIndicator, View } from 'react-native';
import { Redirect, Stack } from 'expo-router';

import { useCurrentUser } from '../../lib/auth';

export default function AppLayout() {
  const { user, loading } = useCurrentUser();

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#fff" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/sign-in" />;
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
