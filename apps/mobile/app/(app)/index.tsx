import { Link } from 'expo-router';
import { Text, View } from 'react-native';

// Dashboard placeholder. The full signed-in dashboard (coverage tiles, copay
// tiles, Amount Saved YTD, four quick actions, Chat CTA) lands in Phase 2 once
// the runtime returns real data shapes.
export default function DashboardScreen() {
  const firstName = 'there';
  return (
    <View className="flex-1 items-center justify-center bg-navy-deep px-6">
      <Text className="text-center text-3xl font-bold text-white">
        Welcome back, {firstName}.
      </Text>
      <Text className="mt-4 max-w-md text-center text-base leading-relaxed text-white/70">
        Dashboard coming online in Phase 2 — check the Phase 0 spec for the full layout.
      </Text>
      <Link href="/settings" style={{ color: '#3DAA7E', marginTop: 32, fontWeight: '600' }}>
        Settings →
      </Link>
      <Link href="/sign-in" style={{ color: 'rgba(255,255,255,0.5)', marginTop: 10 }}>
        Sign-in screen →
      </Link>
    </View>
  );
}
