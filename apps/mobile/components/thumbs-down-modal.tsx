/**
 * ThumbsDownModal (Phase 2J) — structured-reason picker shown after a
 * thumbs-down. Multi-select chips + optional free text. "Skip" dismisses
 * without a structured event (the thumbs-down itself still posts); "Submit"
 * posts the structured_correction event.
 */

import { useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { STRUCTURED_REASON_LABELS, StructuredReason } from '@tyndale/shared';

export function ThumbsDownModal({
  visible,
  onSkip,
  onSubmit,
}: {
  visible: boolean;
  onSkip: () => void;
  onSubmit: (reasons: StructuredReason[], freeText: string | null) => void;
}) {
  const [selected, setSelected] = useState<StructuredReason[]>([]);
  const [text, setText] = useState('');

  const toggle = (r: StructuredReason) =>
    setSelected((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const submit = () => {
    onSubmit(selected, text.trim() || null);
    setSelected([]);
    setText('');
  };
  const skip = () => {
    setSelected([]);
    setText('');
    onSkip();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={skip}>
      <View className="flex-1 justify-end bg-black/50">
        <View className="rounded-t-3xl bg-navy-soft p-6">
          <Text className="text-xl font-bold text-white">What was wrong?</Text>
          <Text className="mt-1 text-sm text-white/60">
            Your feedback helps Tyndale get better. (Optional)
          </Text>

          <ScrollView className="mt-4 max-h-64">
            <View className="flex-row flex-wrap gap-2">
              {STRUCTURED_REASON_LABELS.map(({ value, label }) => {
                const on = selected.includes(value);
                return (
                  <Pressable
                    key={value}
                    onPress={() => toggle(value)}
                    className={
                      on
                        ? 'rounded-full border border-sage bg-sage/20 px-3 py-2'
                        : 'rounded-full border border-white/15 bg-white/5 px-3 py-2'
                    }
                  >
                    <Text className={on ? 'text-xs font-semibold text-white' : 'text-xs text-white/70'}>
                      {label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            <TextInput
              value={text}
              onChangeText={(t) => setText(t.slice(0, 500))}
              placeholder="Tell us more (optional)"
              placeholderTextColor="rgba(255,255,255,0.35)"
              multiline
              className="mt-4 min-h-[72px] rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
            />
          </ScrollView>

          <View className="mt-5 flex-row gap-3">
            <Pressable onPress={skip} className="flex-1 rounded-xl bg-white/5 px-4 py-3">
              <Text className="text-center text-sm font-semibold text-white/70">Skip</Text>
            </Pressable>
            <Pressable onPress={submit} className="flex-1 rounded-xl bg-sage px-4 py-3">
              <Text className="text-center text-sm font-bold text-ink">Submit</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}
