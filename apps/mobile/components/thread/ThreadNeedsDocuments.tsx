/**
 * needs_documents in the chat thread (DL-91). TRUE have/need state per item (DL-90 per-item API),
 * per-item how-to, and an inline "add a document" scoped to THIS case. Satisfied items show
 * checked; once all are satisfied the upload route auto-re-runs the audit (wired in the
 * needs-documents UX fix) and the bridge renders the re-run in the thread.
 */
import { CheckCircle2, Circle, Plus } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { NeedsDocumentsPayload, UnlockMorePayload } from '@tyndale/shared';

export function ThreadNeedsDocuments({
  payload,
  caseFileId,
  unlock = false,
}: {
  payload: NeedsDocumentsPayload | UnlockMorePayload;
  caseFileId: string;
  /** Rung-2 unlock-more framing: the audit is DONE; these items deepen it. Same have/need
   *  component — only the surrounding voice differs (the intro/hint come from the server). */
  unlock?: boolean;
}) {
  const router = useRouter();
  const hint = unlock && 'item_hint' in payload ? payload.item_hint : null;
  return (
    <View
      className="my-2 w-full rounded-2xl border border-accent bg-accent-tint p-5"
      testID={unlock ? 'unlock-more-card' : 'needs-documents-card'}
    >
      <Text className="mb-3 text-base leading-6 text-primary">{payload.intro}</Text>
      {hint ? <Text className="mb-3 text-caption text-secondary">{hint}</Text> : null}
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
            <>
              <Text className="ml-6 text-body leading-6 text-secondary">{d.how_to_get}</Text>
              <Pressable
                onPress={() =>
                  router.push({ pathname: '/upload', params: { caseId: caseFileId, expect: d.key } })
                }
                className="ml-6 mt-2 min-h-[44px] flex-row items-center gap-1.5 self-start rounded-xl border border-accent px-4"
                testID={`needs-add-${d.key}`}
              >
                <Plus size={15} color="var(--c-accent)" />
                <Text className="text-body font-semibold text-accent">Add</Text>
              </Pressable>
            </>
          )}
        </View>
      ))}
      {/* Overall fallback — the per-item Add buttons above are the primary path (each opens
          the upload flow pre-tagged with the document type it should satisfy). */}
      <Pressable
        onPress={() => router.push({ pathname: '/upload', params: { caseId: caseFileId } })}
        className="mt-4 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3"
      >
        <Text className="text-center text-base font-bold text-on-accent">Add a document</Text>
      </Pressable>
    </View>
  );
}
