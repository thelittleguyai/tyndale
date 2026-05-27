import { Link } from 'expo-router';
import { Text, View } from 'react-native';

// Settings placeholder. The improvement-consent toggle (off by default per the
// legal pack) wires up in Phase 4 once the feedback loop ships.
export default function SettingsScreen() {
  return (
    <View className="flex-1 bg-navy-deep px-6 pt-12">
      <Text className="text-2xl font-bold text-white">Settings</Text>
      <View className="mt-6 rounded-lg border border-line-dark bg-navy-soft p-4">
        <Text className="text-base font-semibold text-white">Improve Tyndale with my data</Text>
        <Text className="mt-1 text-sm leading-relaxed text-white/60">
          Off by default. The improvement-consent toggle wires up in Phase 4 once the feedback
          loop is implemented.
        </Text>
        <Text className="mt-3 text-xs font-semibold uppercase tracking-wider text-amber">
          Toggle inactive in this scaffold
        </Text>
      </View>
      <Link href="/" style={{ color: '#3DAA7E', marginTop: 28, fontWeight: '600' }}>
        ← Back to dashboard
      </Link>
    </View>
  );
}
