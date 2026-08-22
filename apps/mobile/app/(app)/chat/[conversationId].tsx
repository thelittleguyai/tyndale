/** Freeform conversation view (Phase CO-10). */

import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { ChatThread } from '../../../components/chat/ChatThread';
import { FreeformOpener } from '../../../components/chat/FreeformOpener';
import { getConversation } from '../../../lib/api-client';

export default function ConversationScreen() {
  const params = useLocalSearchParams<{ conversationId: string }>();
  const id = String(params.conversationId);
  const [title, setTitle] = useState<string | null>(null);

  useEffect(() => {
    getConversation(id)
      .then((c) => setTitle(c.title))
      .catch(() => undefined);
  }, [id]);

  return (
    <View className="flex-1 bg-page">
      <View className="flex-row items-center justify-between border-b border-hairline bg-surface px-4 py-3">
        <Link href="/chat" asChild>
          <Pressable className="flex-row items-center gap-1">
            <ChevronLeft size={18} color="var(--c-text-secondary)" />
            <Text className="text-sm text-secondary">Chats</Text>
          </Pressable>
        </Link>
        <Text className="flex-1 px-3 text-center text-sm font-bold text-primary" numberOfLines={1}>
          {title || 'Ask Tyndale'}
        </Text>
        <View className="w-12" />
      </View>
      {/* Item 4 (2026-08-22): a scripted opener + choice chips replaces the static empty
          state. Client-rendered; the first tap/typed line becomes the first user turn. */}
      <ChatThread
        conversationId={id}
        emptyState={(onSuggest) => <FreeformOpener onChip={onSuggest} />}
      />
    </View>
  );
}
