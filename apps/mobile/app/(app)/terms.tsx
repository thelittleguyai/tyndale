import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export default function TermsPlaceholder() {
  const router = useRouter();
  return (
    <View className="flex-1 bg-navy-deep p-6">
      <Pressable onPress={() => router.back()} className="mb-8 self-start">
        <Text className="text-sm text-white/60">← Back</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-white">Terms of Service</Text>
      <Text className="mt-4 text-base leading-relaxed text-white/70">
        The full Terms of Service are published at launch (Phase 7), after counsel review.
        Improvement-data consent is presented separately from these Terms and is never bundled into
        Terms acceptance.
      </Text>
    </View>
  );
}
