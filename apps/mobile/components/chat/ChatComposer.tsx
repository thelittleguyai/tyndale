/** Composer: multi-line input + send button (→ stop button while streaming).
 *  Web: Enter sends, Shift+Enter inserts a newline. Centered max-width column. */

import { Send, Square } from 'lucide-react-native';
import { useState } from 'react';
import {
  NativeSyntheticEvent,
  Platform,
  Pressable,
  Text,
  TextInput,
  TextInputKeyPressEventData,
  View,
} from 'react-native';

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

  // Web only: Enter sends, Shift+Enter newlines. Native uses the send button.
  const onKeyPress = (e: NativeSyntheticEvent<TextInputKeyPressEventData>) => {
    if (Platform.OS !== 'web') return;
    const ne = e.nativeEvent as TextInputKeyPressEventData & { shiftKey?: boolean };
    if (ne.key === 'Enter' && !ne.shiftKey) {
      e.preventDefault?.();
      submit();
    }
  };

  return (
    <View className="border-t border-white/10 bg-navy-soft px-3 py-3">
      <View className="w-full max-w-3xl flex-row items-end gap-2 self-center">
        <View className="flex-1 justify-center rounded-2xl border border-white/10 bg-navy-deep px-4 py-2.5">
          <TextInput
            value={text}
            onChangeText={setText}
            onKeyPress={onKeyPress}
            placeholder="Ask about your bill, coverage, codes, appeals…"
            placeholderTextColor="rgba(255,255,255,0.35)"
            multiline
            maxLength={8000}
            editable={!streaming}
            className="text-base text-white"
            style={{ minHeight: 24, maxHeight: 140, lineHeight: 22 }}
          />
        </View>
        {streaming ? (
          <Pressable
            onPress={onStop}
            accessibilityRole="button"
            accessibilityLabel="Stop generating"
            className="h-11 w-11 items-center justify-center rounded-full bg-rose"
          >
            <Square size={15} color="#fff" fill="#fff" />
          </Pressable>
        ) : (
          <Pressable
            onPress={submit}
            disabled={!canSend}
            accessibilityRole="button"
            accessibilityLabel="Send message"
            className={`h-11 w-11 items-center justify-center rounded-full ${canSend ? 'bg-sage' : 'bg-white/10'}`}
          >
            <Send size={17} color={canSend ? '#0A1E1C' : 'rgba(255,255,255,0.4)'} />
          </Pressable>
        )}
      </View>
      {text.length > 600 ? (
        <Text className="mt-1 w-full max-w-3xl self-center text-right text-[10px] text-white/30">
          {text.length}/8000
        </Text>
      ) : null}
    </View>
  );
}
