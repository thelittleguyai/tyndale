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
        <View className="rounded-t-3xl bg-surface p-6">
          <Text className="text-xl font-bold text-primary">What was wrong?</Text>
          <Text className="mt-1 text-sm text-secondary">
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
                        ? 'rounded-full border border-accent bg-accent-tint px-3 py-2'
                        : 'rounded-full border border-hairline bg-inset px-3 py-2'
                    }
                  >
                    <Text className={on ? 'text-xs font-semibold text-primary' : 'text-xs text-secondary'}>
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
              className="mt-4 min-h-[72px] rounded-lg border border-hairline bg-inset px-3 py-2 text-sm text-primary"
            />
          </ScrollView>

          <View className="mt-5 flex-row gap-3">
            <Pressable onPress={skip} className="flex-1 rounded-xl bg-inset px-4 py-3">
              <Text className="text-center text-sm font-semibold text-secondary">Skip</Text>
            </Pressable>
            <Pressable onPress={submit} className="flex-1 rounded-xl bg-accent px-4 py-3">
              <Text className="text-center text-sm font-bold text-on-accent">Submit</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}
