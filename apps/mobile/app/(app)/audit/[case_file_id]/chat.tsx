/** Per-case chat tab (Phase CO-10). Finds-or-creates a per-case conversation for
 *  this case, then renders the shared ChatThread scoped to it. */

import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { ChatThread } from '../../../../components/chat/ChatThread';
import { createConversation, listConversations } from '../../../../lib/api-client';

export default function CaseChatScreen() {
  const params = useLocalSearchParams<{ case_file_id: string }>();
  const caseId = String(params.case_file_id);
  const [convId, setConvId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listConversations({ case_id: caseId, mode: 'per_case', limit: 1 });
        const existing = list.conversations[0];
        const id = existing
          ? existing.conversation_id
          : (await createConversation(caseId)).conversation_id;
        if (!cancelled) setConvId(id);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  return (
    <View className="flex-1 bg-page">
      <View className="flex-row items-center justify-between border-b border-hairline bg-surface px-4 py-3">
        <Link href={`/audit/${caseId}`} asChild>
          <Pressable className="flex-row items-center gap-1">
            <ChevronLeft size={18} color="var(--c-text-secondary)" />
            <Text className="text-sm text-secondary">Case</Text>
          </Pressable>
        </Link>
        <Text className="text-sm font-bold text-primary">Chat about this case</Text>
        <View className="w-12" />
      </View>
      {error ? (
        <View className="flex-1 items-center justify-center p-6">
          <Text className="text-danger">{error}</Text>
        </View>
      ) : !convId ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color="var(--c-text-primary)" />
        </View>
      ) : (
        <ChatThread
          conversationId={convId}
          emptyState={(onSuggest) => <CaseEmptyState onSuggest={onSuggest} />}
        />
      )}
    </View>
  );
}

function CaseEmptyState({ onSuggest }: { onSuggest: (text: string) => void }) {
  const suggestions = [
    'Why did insurance only cover this much?',
    'Is this charge legitimate?',
    'What can I do about this?',
  ];
  return (
    <View className="px-2 py-8">
      <Text className="mb-3 text-center text-base font-semibold text-primary">
        Start a conversation about this case
      </Text>
      {suggestions.map((s) => (
        <Pressable
          key={s}
          onPress={() => onSuggest(s)}
          className="mb-2 self-center rounded-full border border-hairline bg-surface px-4 py-2 hover:border-hairline"
        >
          <Text className="text-sm text-secondary">{s}</Text>
        </Pressable>
      ))}
    </View>
  );
}
