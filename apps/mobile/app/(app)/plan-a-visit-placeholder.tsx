import { Pressable, Text } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '../../components/ui/Screen';

export default function PlanAVisitPlaceholder() {
  const router = useRouter();
  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 24, flexGrow: 1 }}>
      <Pressable
        onPress={() => router.back()}
        className="mb-8 min-h-[44px] justify-center self-start"
      >
        <Text className="text-sm text-secondary">← Back to dashboard</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-primary">Plan a Visit</Text>
      <Text className="mt-4 text-base leading-relaxed text-secondary">
        Pre-visit coverage assurance ships in Full V1. For V1-Lite, we recommend uploading
        the bill after your visit for a full audit.
      </Text>
      <Pressable
        onPress={() => router.push('/upload')}
        className="mt-8 min-h-[44px] justify-center self-start rounded-md bg-accent px-4 py-3"
      >
        <Text className="text-sm font-bold text-on-accent">Check a bill instead</Text>
      </Pressable>
      <Text className="mt-10 text-center text-xs text-faint">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </Screen>
  );
}
