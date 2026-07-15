/**
 * The confirm prompt for a free-text mapping (D4b, DL-91). Renders the script-keyed prompt + one
 * confirming tap that commits ALL pre-selections from this mapping event. Nothing is committed
 * until this tap (the cards above show the pre-selection in their "suggested" state). Once
 * confirmed (or superseded by newer text) the button disappears.
 */
import { Pressable, Text, View } from 'react-native';

import type { VerificationSuggestionPayload } from '@tyndale/shared';

export function ThreadSuggestion({
  payload,
  active,
  onConfirm,
}: {
  payload: VerificationSuggestionPayload;
  active: boolean; // false once confirmed or superseded
  onConfirm: () => void;
}) {
  return (
    <View className="my-2 w-full rounded-2xl border border-accent bg-accent-tint p-4">
      <Text className="text-[15px] leading-6 text-primary">{payload.text}</Text>
      {active ? (
        <Pressable
          onPress={onConfirm}
          className="mt-3 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3"
        >
          <Text className="text-center text-base font-bold text-on-accent">Confirm</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
