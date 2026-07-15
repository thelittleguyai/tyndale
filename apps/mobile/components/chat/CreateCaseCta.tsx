/** Rendered when a freeform assistant message includes a create_case_cta action.
 *  Navigates to the upload / case-create flow, preserving the conversation id. */

import { useRouter } from 'expo-router';
import { FilePlus2 } from 'lucide-react-native';
import { Pressable, Text } from 'react-native';

export function CreateCaseCta({ conversationId }: { conversationId: string }) {
  const router = useRouter();
  return (
    <Pressable
      onPress={() =>
        router.push({ pathname: '/upload', params: { fromConversation: conversationId } })
      }
      accessibilityRole="button"
      className="mt-3 flex-row items-center gap-2 self-start rounded-xl bg-accent px-4 py-2.5"
    >
      <FilePlus2 size={16} color="var(--c-on-accent)" />
      <Text className="text-sm font-bold text-on-accent">Upload documents &amp; create a case</Text>
    </Pressable>
  );
}
