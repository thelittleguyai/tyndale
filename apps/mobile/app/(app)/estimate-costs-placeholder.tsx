import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export default function EstimateCostsPlaceholder() {
  const router = useRouter();
  return (
    <View className="flex-1 bg-navy-deep p-6">
      <Pressable onPress={() => router.back()} className="mb-8 self-start">
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-white">Estimate Costs</Text>
      <Text className="mt-4 text-base leading-relaxed text-white/70">
        Cost estimation is being wired against public data sources (Medicare RVU baseline +
        hospital transparency files). Ships in Phase 2G + Phase 5.
      </Text>
      <Text className="absolute bottom-6 left-6 right-6 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </View>
  );
}
