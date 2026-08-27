/** Composer: auto-growing multi-line input + send button (→ stop button while
 *  streaming). The input collapses to a single line at rest and grows with
 *  content up to a cap, then scrolls. Web: Enter sends, Shift+Enter inserts a
 *  newline, and we draw our own focus ring (the browser default clashes with the
 *  dark theme). Centered max-width column. */

import { Paperclip, Send, Square } from 'lucide-react-native';
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
import { useThemeColors } from '../../theme/useThemeColors';

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
  onAttach,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  disabled?: boolean;
  /** Upload-a-bill affordance (2026-08-22): a paperclip left of the input. The thread
   *  decides where it goes — a new case (freeform) or the conversation's case (per-case). */
  onAttach?: () => void;
}) {
  const c = useThemeColors();
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
        {onAttach ? (
          <PressableScale
            onPress={onAttach}
            accessibilityRole="button"
            accessibilityLabel="Upload a bill"
            testID="composer-attach"
            className="h-11 w-11 items-center justify-center rounded-full bg-inset hover:bg-accent-tint"
          >
            <Paperclip size={18} color={c.text.secondary} />
          </PressableScale>
        ) : null}
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
            placeholderTextColor={c.text.faint}
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
            <Square size={15} color={c.text.primary} fill={c.text.primary} />
          </PressableScale>
        ) : (
          <PressableScale
            onPress={submit}
            disabled={!canSend}
            accessibilityRole="button"
            accessibilityLabel="Send message"
            className={`h-11 w-11 items-center justify-center rounded-full ${canSend ? 'bg-accent hover:bg-accent' : 'bg-inset'}`}
          >
            <Send size={17} color={canSend ? c.onAccent : c.text.faint} />
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
