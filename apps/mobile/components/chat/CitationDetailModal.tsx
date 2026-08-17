/** Modal showing a clicked citation in full (title / url / snippet / date / payer).
 *  DL-54: a CPT citation shows the code number with a generic placeholder, never
 *  the AMA-copyrighted descriptor. */

import { ExternalLink, X } from 'lucide-react-native';
import { Linking, Modal, Pressable, ScrollView, Text, View } from 'react-native';

import type { ChatCitation } from '@tyndale/shared';

function Field({ label, value }: { label: string; value: string }) {
  return (
    <View className="mb-3">
      <Text className="mb-0.5 text-[11px] text-faint">{label}</Text>
      <Text className="text-body text-primary">{value}</Text>
    </View>
  );
}

export function CitationDetailModal({
  citation,
  onClose,
}: {
  citation: ChatCitation | null;
  onClose: () => void;
}) {
  const c = citation;
  return (
    <Modal visible={!!c} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        className="flex-1 items-center justify-center bg-black/60 p-6"
      >
        {c ? (
          <Pressable
            onPress={() => undefined}
            className="max-h-[80%] w-full max-w-xl rounded-2xl border border-hairline bg-surface p-5"
          >
            <View className="mb-3 flex-row items-start justify-between gap-3">
              <Text className="flex-1 text-base font-bold text-primary">
                {c.title || 'Source'}
              </Text>
              <Pressable onPress={onClose} hitSlop={8}>
                <X size={18} color="var(--c-text-secondary)" />
              </Pressable>
            </View>
            <ScrollView>
              {c.snippet ? <Field label="Excerpt" value={c.snippet} /> : null}
              {c.effective_date ? <Field label="Effective date" value={c.effective_date} /> : null}
              {c.payer ? <Field label="Payer" value={c.payer} /> : null}
              {c.cpt_code ? (
                <Field
                  label="CPT code"
                  value={`${c.cpt_code} — descriptor omitted (AMA-licensed)`}
                />
              ) : null}
              {c.url ? (
                <Pressable
                  onPress={() => Linking.openURL(c.url as string).catch(() => undefined)}
                  className="mt-1 flex-row items-center gap-2 self-start rounded-lg border border-hairline px-3 py-2"
                >
                  <ExternalLink size={14} color="var(--c-accent)" />
                  <Text className="text-xs font-semibold text-accent">Open source in browser</Text>
                </Pressable>
              ) : null}
            </ScrollView>
          </Pressable>
        ) : null}
      </Pressable>
    </Modal>
  );
}
