import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export default function PrivacyPlaceholder() {
  const router = useRouter();
  return (
    <View className="flex-1 bg-navy-deep p-6">
      <Pressable onPress={() => router.back()} className="mb-8 self-start">
        <Text className="text-sm text-white/60">← Back</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-white">Privacy Policy</Text>
      <Text className="mt-4 text-base leading-relaxed text-white/70">
        The full Privacy Policy is published at launch (Phase 7), after counsel review. Tyndale is a
        non-HIPAA-covered consumer-health app governed by the FTC Act, the FTC Health Breach
        Notification Rule, and state privacy/health-data laws.
      </Text>
    </View>
  );
}
