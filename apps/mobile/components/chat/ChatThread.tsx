/** Composite chat thread (message list + tool indicators + composer + citation
 *  modal) used by BOTH the per-case chat tab and the freeform conversation view. */

import { useRef, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';

import type { ChatCitation, Message } from '@tyndale/shared';

import { ChatComposer } from './ChatComposer';
import { ChatMessage } from './ChatMessage';
import { useChatStream } from './ChatStream';
import { CitationDetailModal } from './CitationDetailModal';
import { ToolCallIndicator } from './ToolCallIndicator';

export function ChatThread({
  conversationId,
  emptyState,
}: {
  conversationId: string;
  // A node, or a render-fn that receives `send` so empty-state suggestion chips are tappable.
  emptyState?: React.ReactNode | ((onSuggest: (text: string) => void) => React.ReactNode);
}) {
  const { messages, streaming, activeTools, error, send, stop } = useChatStream(conversationId);
  const [citation, setCitation] = useState<ChatCitation | null>(null);
  const scrollRef = useRef<ScrollView>(null);

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
    <View className="flex-1 bg-navy-deep">
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
          <ToolCallIndicator tools={activeTools} />
          {error ? <Text className="mt-1 text-xs text-rose">{error}</Text> : null}
        </View>
      </ScrollView>
      <ChatComposer onSend={send} onStop={stop} streaming={streaming} />
      <CitationDetailModal citation={citation} onClose={() => setCitation(null)} />
    </View>
  );
}
