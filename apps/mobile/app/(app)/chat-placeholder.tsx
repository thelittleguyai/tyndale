import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export default function ChatPlaceholder() {
  const router = useRouter();
  return (
    <View className="flex-1 bg-navy-deep p-6">
      <Pressable onPress={() => router.back()} className="mb-8 self-start">
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>
      <Text className="text-3xl font-bold text-white">Chat with AI Assistant</Text>
      <Text className="mt-4 text-base leading-relaxed text-white/70">
        AI chat against the Lead Planner ships post-V1-Lite launch. For now, the Check a
        Bill workflow is the full V1-Lite experience.
      </Text>
      <Pressable
        onPress={() => router.push('/upload')}
        className="mt-8 self-start rounded-md bg-sage px-4 py-3"
      >
        <Text className="text-sm font-bold text-ink">Check a bill instead</Text>
      </Pressable>
      <Text className="absolute bottom-6 left-6 right-6 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </View>
  );
}
