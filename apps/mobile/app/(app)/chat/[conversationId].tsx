/** Freeform conversation view (Phase CO-10). */

import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { ChatThread } from '../../../components/chat/ChatThread';
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
    <View className="flex-1 bg-navy-deep">
      <View className="flex-row items-center justify-between border-b border-white/10 bg-navy-soft px-4 py-3">
        <Link href="/chat" asChild>
          <Pressable className="flex-row items-center gap-1">
            <ChevronLeft size={18} color="rgba(255,255,255,0.7)" />
            <Text className="text-sm text-white/70">Chats</Text>
          </Pressable>
        </Link>
        <Text className="flex-1 px-3 text-center text-sm font-bold text-white" numberOfLines={1}>
          {title || 'Ask Tyndale'}
        </Text>
        <View className="w-12" />
      </View>
      <ChatThread conversationId={id} emptyState={<FreeformEmpty />} />
    </View>
  );
}

function FreeformEmpty() {
  return (
    <View className="px-2 py-10">
      <Text className="text-center text-sm leading-6 text-white/50">
        Ask anything about medical billing — insurance terms, billing codes, your rights,
        appeals. For a specific bill, upload your documents to open a case.
      </Text>
    </View>
  );
}
