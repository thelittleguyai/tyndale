/**
 * needs_documents in the chat thread (DL-91). TRUE have/need state per item (DL-90 per-item API),
 * per-item how-to, and an inline "add a document" scoped to THIS case. Satisfied items show
 * checked; once all are satisfied the upload route auto-re-runs the audit (wired in the
 * needs-documents UX fix) and the bridge renders the re-run in the thread.
 */
import { CheckCircle2, Circle } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { NeedsDocumentsPayload } from '@tyndale/shared';

export function ThreadNeedsDocuments({
  payload,
  caseFileId,
}: {
  payload: NeedsDocumentsPayload;
  caseFileId: string;
}) {
  const router = useRouter();
  return (
    <View className="my-2 w-full rounded-2xl border border-accent bg-accent-tint p-5">
      <Text className="mb-3 text-base leading-6 text-primary">{payload.intro}</Text>
      {payload.items.map((d, i) => (
        <View key={d.key} className={i > 0 ? 'mt-3 border-t border-hairline pt-3' : ''}>
          <View className="mb-1 flex-row items-start gap-2">
            {d.have ? (
              <CheckCircle2 size={18} color="var(--c-accent)" />
            ) : (
              <Circle size={18} color="var(--c-text-faint)" />
            )}
            <Text
              className={`flex-1 text-base font-bold ${d.have ? 'text-faint line-through' : 'text-primary'}`}
            >
              {d.label}
            </Text>
          </View>
          {d.have ? null : (
            <Text className="ml-6 text-sm leading-6 text-secondary">{d.how_to_get}</Text>
          )}
        </View>
      ))}
      <Pressable
        onPress={() => router.push({ pathname: '/upload', params: { caseId: caseFileId } })}
        className="mt-4 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3"
      >
        <Text className="text-center text-base font-bold text-on-accent">Add a document</Text>
      </Pressable>
    </View>
  );
}
