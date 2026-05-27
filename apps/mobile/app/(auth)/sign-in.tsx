import { Link } from 'expo-router';
import { Pressable, Text, View } from 'react-native';
import { track } from '../../lib/analytics';

// Google + Email sign-in stubs. Buttons render and fire the `signin_clicked`
// baseline event, but there is no real OAuth round trip in Phase 1B.
export default function SignInScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-navy-deep px-6">
      <Text className="text-2xl font-bold text-white">Sign in to Tyndale</Text>
      <Text className="mt-3 max-w-sm text-center text-base leading-relaxed text-white/70">
        Google + Email sign-in are scaffolded. Real authentication wires in Phase 2.
      </Text>

      <Pressable
        accessibilityRole="button"
        onPress={() => track('signin_clicked', { method: 'google' })}
        className="mt-8 w-full max-w-xs items-center rounded-md bg-white px-6 py-3"
      >
        <Text className="text-base font-semibold text-ink">Continue with Google</Text>
      </Pressable>

      <Pressable
        accessibilityRole="button"
        onPress={() => track('signin_clicked', { method: 'email' })}
        className="mt-3 w-full max-w-xs items-center rounded-md border border-white/25 px-6 py-3"
      >
        <Text className="text-base font-semibold text-white">Continue with Email</Text>
      </Pressable>

      <Text className="mt-6 text-xs text-white/45">No real OAuth round trip in this scaffold.</Text>

      <Link href="/" style={{ color: 'rgba(255,255,255,0.6)', marginTop: 24 }}>
        ← Back
      </Link>
    </View>
  );
}
