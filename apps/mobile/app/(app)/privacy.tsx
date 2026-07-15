import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { buildPrivacyDoc } from '@tyndale/shared';
import { Screen } from '../../components/ui/Screen';
import { LegalDocView } from '../../components/ui/LegalDoc';

// One-line publication gate: flip EXPO_PUBLIC_LEGAL_PUBLISHED to "true" (and
// fill LEGAL_FIELDS in @tyndale/shared/legal) after counsel signs off. Default
// is unpublished, so the DRAFT banner shows until then.
const LEGAL_PUBLISHED = process.env.EXPO_PUBLIC_LEGAL_PUBLISHED === 'true';

export default function PrivacyScreen() {
  const router = useRouter();
  const doc = buildPrivacyDoc();
  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 24, flexGrow: 1 }}>
      <Pressable onPress={() => router.back()} className="mb-8 self-start">
        <Text className="text-sm text-secondary">← Back</Text>
      </Pressable>
      <LegalDocView doc={doc} published={LEGAL_PUBLISHED} />
      <View className="h-16" />
    </Screen>
  );
}
