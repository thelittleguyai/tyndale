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
  Text,
  TextInput,
  TextInputContentSizeChangeEventData,
  TextInputKeyPressEventData,
  TextStyle,
  View,
} from 'react-native';

import { PressableScale } from '../ui/PressableScale';

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
    <View className="border-t border-hairline bg-surface px-3 py-3">
      <View className="w-full max-w-3xl flex-row items-end gap-2 self-center">
        <View
          className={`flex-1 rounded-2xl border bg-page px-4 py-2.5 ${
            focused ? 'border-accent' : 'border-hairline'
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
            className="text-base text-primary"
            style={[{ height: inputHeight, lineHeight: 22 }, webNoOutline]}
          />
        </View>
        {streaming ? (
          <PressableScale
            onPress={onStop}
            accessibilityRole="button"
            accessibilityLabel="Stop generating"
            className="h-11 w-11 items-center justify-center rounded-full bg-danger hover:opacity-90"
          >
            <Square size={15} color="var(--c-text-primary)" fill="#fff" />
          </PressableScale>
        ) : (
          <PressableScale
            onPress={submit}
            disabled={!canSend}
            accessibilityRole="button"
            accessibilityLabel="Send message"
            className={`h-11 w-11 items-center justify-center rounded-full ${canSend ? 'bg-accent hover:bg-accent' : 'bg-inset'}`}
          >
            <Send size={17} color={canSend ? '#0A1E1C' : 'rgba(255,255,255,0.4)'} />
          </PressableScale>
        )}
      </View>
      {text.length > 600 ? (
        <Text className="mt-1 w-full max-w-3xl self-center text-right text-[10px] text-faint">
          {text.length}/8000
        </Text>
      ) : null}
    </View>
  );
}
