import { Stack } from 'expo-router';

// Authenticated group layout (placeholder). The real auth gate lands in Phase 2.
export default function AppLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: '#091621' },
      }}
    />
  );
}
