/**
 * Dispatches one thread Message to its renderer by `kind` (DL-91). 'message' = the classic
 * text/chunks turn (rendered by ChatMessage); the rest are bridge-authored (role='system') cards.
 * The unlock moment card is built (MomentCards) but the SERVER never emits it in Phase A
 * (enable_first_case_unlock is false + the bridge emits no unlock), so it never mounts here.
 */
import { Text, View } from 'react-native';

import type {
  LineItemResponse,
  Message,
  NeedsDocumentsPayload,
  StatusCardPayload,
  SystemMessagePayload,
  ThreeNumberMomentPayload,
  UnlockMomentPayload,
  VerificationRequestPayload,
  VerificationSuggestionPayload,
} from '@tyndale/shared';

import { ChatMessage } from '../chat/ChatMessage';
import type { Draft } from '../../app/(app)/audit/[case_file_id]/encounter';
import { StatusCard } from './StatusCard';
import { ThreeNumberMoment, UnlockMoment } from './MomentCards';
import { ThreadNeedsDocuments } from './ThreadNeedsDocuments';
import { ThreadSuggestion } from './ThreadSuggestion';
import { ThreadVerification } from './ThreadVerification';

function SystemLine({ text, tone }: { text: string; tone?: 'neutral' | 'error' }) {
  return (
    <View className={`my-2 w-full rounded-2xl p-4 ${tone === 'error' ? 'bg-danger-tint' : 'bg-surface-raised'}`}>
      <Text className="text-[15px] leading-6 text-primary">{text}</Text>
    </View>
  );
}

export function ThreadEntry({
  message,
  caseFileId,
  conversationId,
  drafts,
  onRespond,
  onNote,
  activeSuggestionId,
  onConfirmSuggestion,
}: {
  message: Message;
  caseFileId: string;
  conversationId: string;
  drafts: Record<string, Draft>;
  onRespond: (lineItemId: string, r: LineItemResponse) => void;
  onNote: (lineItemId: string, n: string) => void;
  activeSuggestionId?: string | null;
  onConfirmSuggestion?: () => void;
}) {
  const kind = message.kind ?? 'message';
  const payload = (message.payload ?? {}) as Record<string, unknown>;

  switch (kind) {
    case 'verification_suggestion':
      return (
        <ThreadSuggestion
          payload={payload as unknown as VerificationSuggestionPayload}
          active={message.message_id === activeSuggestionId}
          onConfirm={() => onConfirmSuggestion?.()}
        />
      );
    case 'status_card_update':
      return <StatusCard payload={payload as unknown as StatusCardPayload} />;
    case 'moment_card':
      return (payload as { variant?: string }).variant === 'first_case_unlock' ? (
        <UnlockMoment payload={payload as unknown as UnlockMomentPayload} />
      ) : (
        <ThreeNumberMoment payload={payload as unknown as ThreeNumberMomentPayload} />
      );
    case 'verification_request':
      return (
        <ThreadVerification
          payload={payload as unknown as VerificationRequestPayload}
          drafts={drafts}
          onRespond={onRespond}
          onNote={onNote}
        />
      );
    case 'system_message': {
      const p = payload as unknown as SystemMessagePayload & {
        needs_documents?: NeedsDocumentsPayload;
      };
      if (p.needs_documents) {
        return <ThreadNeedsDocuments payload={p.needs_documents} caseFileId={caseFileId} />;
      }
      return <SystemLine text={p.text ?? message.content ?? ''} tone={p.tone} />;
    }
    default:
      return (
        <ChatMessage message={message} conversationId={conversationId} onCitation={() => undefined} />
      );
  }
}
