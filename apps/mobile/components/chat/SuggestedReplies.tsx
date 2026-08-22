/** Tap-to-reply chips (Brock 2026-08-22, item 3). Rendered under the NEWEST assistant
 *  message only. D4(b) rule: the tap is the only state change — it sends the chip's literal
 *  text as the user's message; typed free text still works and takes precedence. The chips
 *  disappear with the user's reply because they only ever hang off the last assistant turn. */

import { Pressable, Text, View } from 'react-native';

export function SuggestedReplies({
  replies,
  onPick,
  disabled,
}: {
  replies: string[];
  onPick: (text: string) => void;
  disabled?: boolean;
}) {
  if (!replies.length) return null;
  return (
    <View className="mb-3 ml-1 flex-row flex-wrap gap-2" testID="suggested-replies">
      {replies.slice(0, 4).map((r) => (
        <Pressable
          key={r}
          onPress={() => onPick(r)}
          disabled={disabled}
          accessibilityRole="button"
          className="min-h-[36px] justify-center rounded-full border border-accent bg-surface px-4 py-1.5 hover:bg-accent-tint active:opacity-70"
        >
          <Text className="text-sm font-semibold text-accent">{r}</Text>
        </Pressable>
      ))}
    </View>
  );
}
