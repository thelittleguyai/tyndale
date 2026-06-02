/** Composer: multi-line input + send button (→ stop button while streaming). */

import { Send, Square } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

export function ChatComposer({
  onSend,
  onStop,
  streaming,
  disabled,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  disabled?: boolean;
}) {
  const [text, setText] = useState('');
  const canSend = !!text.trim() && !streaming && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
  };

  return (
    <View className="border-t border-white/10 bg-navy-soft px-3 py-2.5">
      <View className="flex-row items-end gap-2">
        <View className="flex-1 rounded-2xl border border-white/10 bg-navy-deep px-3 py-1.5">
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Ask about your bill, coverage, codes, appeals…"
            placeholderTextColor="rgba(255,255,255,0.35)"
            multiline
            maxLength={8000}
            editable={!streaming}
            className="max-h-28 text-sm text-white"
            style={{ minHeight: 24 }}
          />
          {text.length > 600 ? (
            <Text className="mt-0.5 text-right text-[10px] text-white/30">{text.length}/8000</Text>
          ) : null}
        </View>
        {streaming ? (
          <Pressable
            onPress={onStop}
            accessibilityRole="button"
            accessibilityLabel="Stop generating"
            className="h-10 w-10 items-center justify-center rounded-full bg-rose"
          >
            <Square size={15} color="#fff" fill="#fff" />
          </Pressable>
        ) : (
          <Pressable
            onPress={submit}
            disabled={!canSend}
            accessibilityRole="button"
            accessibilityLabel="Send message"
            className={`h-10 w-10 items-center justify-center rounded-full ${canSend ? 'bg-sage' : 'bg-white/10'}`}
          >
            <Send size={16} color={canSend ? '#0A1E1C' : 'rgba(255,255,255,0.4)'} />
          </Pressable>
        )}
      </View>
    </View>
  );
}
