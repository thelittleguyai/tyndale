/**
 * Verification cards re-hosted into the chat thread (DL-91, D3/D4a). Renders one group's line
 * items (≤3, grouped server-side) using the SAME LineItemCard as the classic encounter screen.
 * D4b shipped 2026-08-22: free text near a card maps to a pre-selected answer awaiting the
 * confirming tap (verification_mapper + the suggestion entries); taps remain the only writes.
 *
 * e2e round 3 R1: the server refreshes every card with `answered` (the answer on file, wherever
 * it was given) and `awaiting` (the line items still owed an answer). An answered fact renders
 * its answer, locked; an item in neither is no longer one of the case's facts and is not shown.
 * A card no server has refreshed yet (no `awaiting`) keeps the session-drafts behaviour.
 */
import { Text, View } from 'react-native';

import type { LineItem, LineItemResponse, VerificationRequestPayload } from '@tyndale/shared';

import { LineItemCard, type Draft } from '../../app/(app)/audit/[case_file_id]/encounter';

/** The line items a card still owes an answer for — every item on a never-refreshed card. */
export function owedItems(payload: VerificationRequestPayload): LineItem[] {
  const items = payload.line_items ?? [];
  if (!Array.isArray(payload.awaiting)) return items;
  const owed = new Set(payload.awaiting);
  return items.filter((i) => owed.has(i.line_item_id));
}

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
  const answered = payload.answered ?? {};
  const owed = owedItems(payload);
  const owedIds = new Set(owed.map((i) => i.line_item_id));
  const shown = Array.isArray(payload.awaiting)
    ? (payload.line_items ?? []).filter((i) => owedIds.has(i.line_item_id) || answered[i.line_item_id])
    : payload.line_items ?? [];
  if (shown.length === 0) return null;
  return (
    <View className="my-2 w-full" testID={`verification-card-${payload.group_index}`}>
      {payload.group_index === 0 ? (
        <Text className="mb-3 text-base leading-6 text-primary">{payload.intro}</Text>
      ) : null}
      {shown.map((item) => {
        const onFile = owedIds.has(item.line_item_id) ? undefined : answered[item.line_item_id];
        return (
          <LineItemCard
            key={item.line_item_id}
            item={item}
            draft={onFile ? { response: onFile, user_note: '' } : drafts[item.line_item_id] ?? { response: null, user_note: '' }}
            suggested={onFile ? false : drafts[item.line_item_id]?.suggested}
            locked={Boolean(onFile)}
            onRespond={(r) => onRespond(item.line_item_id, r)}
            onNote={(n) => onNote(item.line_item_id, n)}
          />
        );
      })}
      {/* the nudge asks for taps that are still owed — gone once every card is answered (2026-09-23) */}
      {owed.some((item) => !drafts[item.line_item_id]?.response) ? (
        <Text className="mt-1 text-xs italic text-faint" testID="verification-nudge">{payload.nudge}</Text>
      ) : null}
    </View>
  );
}
