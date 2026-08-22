/** Composite chat thread (message list + tool indicators + composer + citation
 *  modal) used by BOTH the per-case chat tab and the freeform conversation view. */

import { useRef, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import type { ChatCitation, Message } from '@tyndale/shared';

import { ChatComposer } from './ChatComposer';
import { ChatMessage } from './ChatMessage';
import { useChatStream } from './ChatStream';
import { CitationDetailModal } from './CitationDetailModal';
import { SuggestedReplies } from './SuggestedReplies';
import { ToolCallIndicator } from './ToolCallIndicator';

export function ChatThread({
  conversationId,
  emptyState,
}: {
  conversationId: string;
  // A node, or a render-fn that receives `send` so empty-state suggestion chips are tappable.
  emptyState?: React.ReactNode | ((onSuggest: (text: string) => void) => React.ReactNode);
}) {
  const { messages, caseId, streaming, activeTools, error, send, stop } =
    useChatStream(conversationId);
  const [citation, setCitation] = useState<ChatCitation | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const router = useRouter();

  // Upload a bill anytime (2026-08-22). Freeform → a NEW case, preserving the conversation
  // exactly like CreateCaseCta; per-case → the documents attach to THIS case (the upload
  // screen already takes caseId).
  const onAttach = () =>
    caseId
      ? router.push({ pathname: '/upload', params: { caseId } })
      : router.push({ pathname: '/upload', params: { fromConversation: conversationId } });

  // Item 3 (2026-08-22): chips hang off the NEWEST assistant turn only, once it's complete.
  const last = messages[messages.length - 1];
  const chips =
    !streaming && last && last.role === 'assistant' && last.status === 'complete'
      ? (last.suggested_replies ?? []).filter((r) => typeof r === 'string' && r.trim())
      : [];

  const onRetry = (m: Message) => {
    const idx = messages.findIndex((x) => x.message_id === m.message_id);
    for (let i = idx - 1; i >= 0; i--) {
      const prior = messages[i];
      if (prior.role === 'user' && prior.content) {
        send(prior.content, true); // retry: don't re-append the user message
        break;
      }
    }
  };

  return (
    <View className="flex-1 bg-page">
      <ScrollView
        ref={scrollRef}
        className="flex-1"
        contentContainerStyle={{ paddingVertical: 16, paddingHorizontal: 16, flexGrow: 1 }}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        keyboardShouldPersistTaps="handled"
      >
        <View className="w-full max-w-3xl self-center">
          {messages.length === 0 && !streaming
            ? typeof emptyState === 'function'
              ? emptyState(send)
              : emptyState
            : null}
          {messages.map((m) => (
            <ChatMessage
              key={m.message_id}
              message={m}
              conversationId={conversationId}
              onCitation={setCitation}
              onRetry={onRetry}
            />
          ))}
          <SuggestedReplies replies={chips} onPick={(text) => send(text)} disabled={streaming} />
          <ToolCallIndicator tools={activeTools} />
          {error ? <Text className="mt-1 text-xs text-danger">{error}</Text> : null}
        </View>
      </ScrollView>
      <ChatComposer onSend={send} onStop={stop} streaming={streaming} onAttach={onAttach} />
      <CitationDetailModal citation={citation} onClose={() => setCitation(null)} />
    </View>
  );
}
