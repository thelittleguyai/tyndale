/**
 * Verification cards re-hosted into the chat thread (DL-91, D3/D4a). Renders one group's line
 * items (≤3, grouped server-side) using the SAME LineItemCard as the classic encounter screen.
 * Phase A is structured taps only (D4a — option a); the script-keyed nudge tells the user to tap.
 * TODO(phase-b): pre-select+confirm from free text (D4b) — map free text near a card to a tap.
 */
import { Text, View } from 'react-native';

import type { LineItemResponse, VerificationRequestPayload } from '@tyndale/shared';

import { LineItemCard, type Draft } from '../../app/(app)/audit/[case_file_id]/encounter';

export function ThreadVerification({
  payload,
  drafts,
  onRespond,
  onNote,
}: {
  payload: VerificationRequestPayload;
  drafts: Record<string, Draft>;
  onRespond: (lineItemId: string, r: LineItemResponse) => void;
  onNote: (lineItemId: string, n: string) => void;
}) {
  return (
    <View className="my-2 w-full">
      {payload.group_index === 0 ? (
        <Text className="mb-3 text-base leading-6 text-white/85">{payload.intro}</Text>
      ) : null}
      {payload.line_items.map((item) => (
        <LineItemCard
          key={item.line_item_id}
          item={item}
          draft={drafts[item.line_item_id] ?? { response: null, user_note: '' }}
          onRespond={(r) => onRespond(item.line_item_id, r)}
          onNote={(n) => onNote(item.line_item_id, n)}
        />
      ))}
      <Text className="mt-1 text-xs italic text-white/45">{payload.nudge}</Text>
    </View>
  );
}
