/** Renders one message: user bubble, or assistant message with tiered A/B/C
 *  rendering, citation chips, confidence badge, and error/stopped states. */

import { AlertTriangle, RotateCcw } from 'lucide-react-native';
import { Pressable, Text, View } from 'react-native';

import type { ChatCitation, ContentChunk, Message } from '@tyndale/shared';

import { CitationChip } from './CitationChip';
import { CreateCaseCta } from './CreateCaseCta';

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const border = value >= 0.75 ? 'border-sage/40' : value >= 0.5 ? 'border-amber/40' : 'border-rose/40';
  const txt = value >= 0.75 ? 'text-sage' : value >= 0.5 ? 'text-amber' : 'text-rose';
  return (
    <View className={`rounded-full border px-2 py-0.5 ${border}`}>
      <Text className={`text-[10px] font-semibold ${txt}`}>{pct}% confident</Text>
    </View>
  );
}

function TierBlock({
  chunk,
  onCitation,
}: {
  chunk: ContentChunk;
  onCitation: (c: ChatCitation) => void;
}) {
  if (chunk.tier === 'C') {
    return (
      <View className="mt-2">
        <Text className="mb-1 text-[10px] uppercase tracking-wide text-white/40">Recommendation</Text>
        <Text className="text-sm italic leading-6 text-white/80">{chunk.text}</Text>
      </View>
    );
  }
  return (
    <View className="mt-2">
      <Text className="text-sm leading-6 text-white/90">{chunk.text}</Text>
      {chunk.tier === 'B' && chunk.citations?.length ? (
        <View className="mt-1.5 flex-row flex-wrap gap-1.5">
          {chunk.citations.map((c, i) => (
            <CitationChip key={i} citation={c} onPress={onCitation} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

export function ChatMessage({
  message,
  conversationId,
  onCitation,
  onRetry,
}: {
  message: Message;
  conversationId: string;
  onCitation: (c: ChatCitation) => void;
  onRetry?: (m: Message) => void;
}) {
  if (message.role === 'user') {
    return (
      <View className="mb-3 items-end">
        <View className="max-w-[85%] rounded-2xl rounded-tr-sm bg-sage px-3.5 py-2.5">
          <Text className="text-sm leading-5 text-ink">{message.content}</Text>
        </View>
      </View>
    );
  }

  const chunks = message.content_chunks || [];
  const allCitations = message.citations || [];
  const hasCta = allCitations.some((c) => c.action_type === 'create_case_cta');
  const footerCitations = chunks.length
    ? []
    : allCitations.filter((c) => c.action_type !== 'create_case_cta');
  const failed = message.status === 'failed';
  const stopped = message.status === 'stopped';
  const cardTone = failed
    ? 'border-rose/40 bg-rose/10'
    : stopped
      ? 'border-amber/40 bg-amber/10'
      : 'border-white/10 bg-navy-soft';

  return (
    <View className="mb-3 items-start">
      <View className={`max-w-[92%] rounded-2xl rounded-tl-sm border px-3.5 py-3 ${cardTone}`}>
        {chunks.length ? (
          chunks.map((ch, i) => <TierBlock key={i} chunk={ch} onCitation={onCitation} />)
        ) : (
          <Text className="text-sm leading-6 text-white/90">
            {message.content || (message.status === 'streaming' ? '…' : '')}
          </Text>
        )}

        {hasCta ? <CreateCaseCta conversationId={conversationId} /> : null}

        {stopped ? <Text className="mt-2 text-xs text-amber">Generation stopped.</Text> : null}

        {failed ? (
          <View className="mt-2 flex-row flex-wrap items-center gap-2">
            <AlertTriangle size={13} color="#C75252" />
            <Text className="text-xs text-rose">
              {message.error_message || 'Something went wrong.'}
            </Text>
            {onRetry ? (
              <Pressable
                onPress={() => onRetry(message)}
                hitSlop={10}
                className="flex-row items-center gap-1 rounded-md border border-white/15 px-2 py-1"
              >
                <RotateCcw size={11} color="rgba(255,255,255,0.7)" />
                <Text className="text-[11px] text-white/70">Retry</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {message.status === 'complete' &&
        (footerCitations.length || message.confidence_overall != null) ? (
          <View className="mt-2.5 flex-row flex-wrap items-center gap-1.5 border-t border-white/5 pt-2">
            {footerCitations.map((c, i) => (
              <CitationChip key={`f${i}`} citation={c} onPress={onCitation} />
            ))}
            {message.confidence_overall != null ? (
              <ConfidenceBadge value={message.confidence_overall} />
            ) : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}
