/**
 * Verification cards re-hosted into the chat thread (DL-91, D3/D4a). Renders one group's line
 * items (≤3, grouped server-side) using the SAME LineItemCard as the classic encounter screen.
 * D4b shipped 2026-08-22: free text near a card maps to a pre-selected answer awaiting the
 * confirming tap (verification_mapper + the suggestion entries); taps remain the only writes.
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
        <Text className="mb-3 text-base leading-6 text-primary">{payload.intro}</Text>
      ) : null}
      {payload.line_items.map((item) => (
        <LineItemCard
          key={item.line_item_id}
          item={item}
          draft={drafts[item.line_item_id] ?? { response: null, user_note: '' }}
          suggested={drafts[item.line_item_id]?.suggested}
          onRespond={(r) => onRespond(item.line_item_id, r)}
          onNote={(n) => onNote(item.line_item_id, n)}
        />
      ))}
      {/* the nudge asks for taps that are still owed — gone once every card is answered (2026-09-23) */}
      {payload.line_items.some((item) => !drafts[item.line_item_id]?.response) ? (
        <Text className="mt-1 text-xs italic text-faint" testID="verification-nudge">{payload.nudge}</Text>
      ) : null}
    </View>
  );
}
