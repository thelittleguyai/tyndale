/** Composer: auto-growing multi-line input + send button (→ stop button while
 *  streaming). The input collapses to a single line at rest and grows with
 *  content up to a cap, then scrolls. Web: Enter sends, Shift+Enter inserts a
 *  newline, and we draw our own focus ring (the browser default clashes with the
 *  dark theme). Centered max-width column. */

import { Send, Square } from 'lucide-react-native';
import { useState } from 'react';
import {
  NativeSyntheticEvent,
  Platform,
  Pressable,
  Text,
  TextInput,
  TextInputContentSizeChangeEventData,
  TextInputKeyPressEventData,
  TextStyle,
  View,
} from 'react-native';

const MIN_INPUT_H = 24; // ~one line at lineHeight 22
const MAX_INPUT_H = 140; // ~6 lines, then the input scrolls internally

// react-native-web renders `multiline` as a <textarea>, which gets a default
// blue focus outline. We draw our own focus border on the wrapper instead.
const webNoOutline =
  Platform.OS === 'web' ? ({ outlineStyle: 'none' } as unknown as TextStyle) : null;

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
  const [inputHeight, setInputHeight] = useState(MIN_INPUT_H);
  const [focused, setFocused] = useState(false);
  const canSend = !!text.trim() && !streaming && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
    setInputHeight(MIN_INPUT_H); // collapse back to one line after sending
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

  // Grow the input to fit its content, clamped to [MIN, MAX].
  const onContentSizeChange = (
    e: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    const h = e.nativeEvent.contentSize.height;
    setInputHeight(Math.max(MIN_INPUT_H, Math.min(MAX_INPUT_H, h)));
  };

  return (
    <View className="border-t border-white/10 bg-navy-soft px-3 py-3">
      <View className="w-full max-w-3xl flex-row items-end gap-2 self-center">
        <View
          className={`flex-1 rounded-2xl border bg-navy-deep px-4 py-2.5 ${
            focused ? 'border-sage/60' : 'border-white/10'
          }`}
        >
          <TextInput
            value={text}
            onChangeText={setText}
            onKeyPress={onKeyPress}
            onContentSizeChange={onContentSizeChange}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask about your bill, coverage, codes, appeals…"
            placeholderTextColor="rgba(255,255,255,0.35)"
            multiline
            maxLength={8000}
            editable={!streaming}
            className="text-base text-white"
            style={[{ height: inputHeight, lineHeight: 22 }, webNoOutline]}
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
