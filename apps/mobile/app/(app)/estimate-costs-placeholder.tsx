import { Pressable, Text } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '../../components/ui/Screen';

export default function EstimateCostsPlaceholder() {
  const router = useRouter();
  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 24, flexGrow: 1 }}>
      <Pressable
        onPress={() => router.back()}
        className="mb-8 min-h-[44px] justify-center self-start"
      >
        <Text className="text-sm text-secondary">← Back to dashboard</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-primary">Estimate Costs</Text>
      <Text className="mt-4 text-base leading-relaxed text-secondary">
        Cost estimation is being wired against public data sources (Medicare RVU baseline +
        hospital transparency files). Ships in Phase 2G + Phase 5.
      </Text>
      <Text className="mt-10 text-center text-xs text-faint">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </Screen>
  );
}
