/**
 * ThumbsRating (Phase 2J) — up/down on a finding or the composed response.
 *
 * - thumbs-up: posts a thumbs event immediately.
 * - thumbs-down: opens ThumbsDownModal; the thumbs-down posts regardless of
 *   whether the user fills in the structured reason (Skip still posts the
 *   thumbs-down per the spec), and a structured_correction event posts too if
 *   they Submit reasons.
 * - state is seeded from existingRating (restored via GET /v1/feedback/case/{id})
 *   so a refresh keeps the rating.
 */

import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ThumbsDown, ThumbsUp } from 'lucide-react-native';

import {
  StructuredReason,
  ThumbsValue,
  makeFeedbackEvent,
  submitFeedback,
} from '../lib/api-client';
import { ThumbsDownModal } from './thumbs-down-modal';

export function ThumbsRating({
  target,
  caseFileId,
  existingRating = null,
  size = 18,
}: {
  target: { type: 'finding' | 'response'; id: string };
  caseFileId: string;
  existingRating?: ThumbsValue | null;
  size?: number;
}) {
  const [rating, setRating] = useState<ThumbsValue | null>(existingRating);
  const [modalOpen, setModalOpen] = useState(false);

  const postThumb = async (thumbs: ThumbsValue) => {
    setRating(thumbs); // optimistic
    try {
      await submitFeedback(
        makeFeedbackEvent({
          case_file_id: caseFileId,
          feedback_type: 'thumbs',
          response_id: target.id,
          thumbs,
        }),
      );
    } catch {
      // leave optimistic state; a transient failure shouldn't nuke the UI
    }
  };

  const onUp = () => postThumb('up');
  const onDown = () => {
    // The thumbs-down posts immediately; the modal collects optional detail.
    postThumb('down');
    setModalOpen(true);
  };

  const onSubmitReasons = async (reasons: StructuredReason[], freeText: string | null) => {
    setModalOpen(false);
    if (reasons.length === 0 && !freeText) return; // nothing extra to record
    try {
      await submitFeedback(
        makeFeedbackEvent({
          case_file_id: caseFileId,
          feedback_type: 'structured_correction',
          response_id: target.id,
          structured_reason: reasons.length ? reasons : null,
          free_text: freeText,
        }),
      );
    } catch {
      /* best-effort */
    }
  };

  return (
    <View className="flex-row items-center gap-2">
      <Pressable
        onPress={onUp}
        accessibilityLabel="Helpful"
        className={
          rating === 'up'
            ? 'rounded-md bg-sage/20 p-1.5'
            : 'rounded-md bg-white/5 p-1.5'
        }
      >
        <ThumbsUp size={size} color={rating === 'up' ? '#3DAA7E' : 'rgba(255,255,255,0.5)'} />
      </Pressable>
      <Pressable
        onPress={onDown}
        accessibilityLabel="Not helpful"
        className={
          rating === 'down'
            ? 'rounded-md bg-rose/20 p-1.5'
            : 'rounded-md bg-white/5 p-1.5'
        }
      >
        <ThumbsDown size={size} color={rating === 'down' ? '#C75252' : 'rgba(255,255,255,0.5)'} />
      </Pressable>

      <ThumbsDownModal
        visible={modalOpen}
        onSkip={() => setModalOpen(false)}
        onSubmit={onSubmitReasons}
      />
    </View>
  );
}
