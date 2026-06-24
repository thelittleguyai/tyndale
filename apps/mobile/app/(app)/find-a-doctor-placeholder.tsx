import { Pressable, Text } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '../../components/ui/Screen';

export default function FindADoctorPlaceholder() {
  const router = useRouter();
  return (
    <Screen className="flex-1 bg-navy-deep" contentContainerStyle={{ padding: 24, flexGrow: 1 }}>
      <Pressable
        onPress={() => router.back()}
        className="mb-8 min-h-[44px] justify-center self-start"
      >
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-white">Find a Doctor</Text>
      <Text className="mt-4 text-base leading-relaxed text-white/70">
        In-network provider search ships in Full V1. For V1-Lite, your insurer's online
        directory is the most up-to-date source.
      </Text>
      <Text className="mt-10 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </Screen>
  );
}
