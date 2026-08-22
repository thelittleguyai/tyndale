/** Freeform "Ask Tyndale" conversation list (Phase CO-10). */

import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { Link, useRouter } from 'expo-router';
import { ChevronLeft, MessageSquare, Plus } from 'lucide-react-native';

import type { Conversation } from '@tyndale/shared';

import { createConversation, getSurfaceCopy, listConversations } from '../../../lib/api-client';
import { OPENER_FALLBACK } from '../../../components/chat/FreeformOpener';
import { PressableScale } from '../../../components/ui/PressableScale';
import { ScreenView } from '../../../components/ui/Screen';

export default function ChatListScreen() {
  const router = useRouter();
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [opener, setOpener] = useState<string>(OPENER_FALLBACK);
  useEffect(() => {
    getSurfaceCopy('chat')
      .then((c) => c.opener && setOpener(c.opener))
      .catch(() => {/* fallback renders */});
  }, []);

  const load = useCallback(() => {
    listConversations({ mode: 'freeform', limit: 50 })
      .then((r) => setItems(r.conversations))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => load(), [load]);

  const start = async () => {
    try {
      const c = await createConversation();
      router.push(`/chat/${c.conversation_id}`);
    } catch {
      /* ignore */
    }
  };

  return (
    <View className="flex-1 bg-page">
      <View className="flex-row items-center justify-between border-b border-hairline bg-surface px-4 py-3">
        <Link href="/" asChild>
          <Pressable className="min-h-[44px] flex-row items-center gap-1 active:opacity-70">
            <ChevronLeft size={18} color="var(--c-text-secondary)" />
            <Text className="text-sm text-secondary hover:text-primary">Home</Text>
          </Pressable>
        </Link>
        <Text className="text-base font-bold text-primary">Ask Tyndale</Text>
        <PressableScale
          onPress={start}
          className="min-h-[44px] flex-row items-center gap-1 rounded-full bg-accent px-3 py-1.5 hover:bg-accent"
        >
          <Plus size={14} color="var(--c-on-accent)" />
          <Text className="text-xs font-bold text-on-accent">New</Text>
        </PressableScale>
      </View>

      <ScrollView className="flex-1 px-4" contentContainerStyle={{ paddingVertical: 16 }}>
        <ScreenView>
          {loading ? <ActivityIndicator color="var(--c-text-primary)" className="mt-8" /> : null}

          {!loading && items.length === 0 ? (
            <View className="mt-6 rounded-2xl border border-hairline bg-surface p-5 shadow-card">
              <Text className="text-body leading-6 text-secondary">{opener}</Text>
              <PressableScale
                onPress={start}
                className="mt-4 min-h-[44px] justify-center self-start rounded-xl bg-accent px-4 py-2.5 hover:bg-accent"
              >
                <Text className="text-body font-bold text-on-accent">Start a conversation</Text>
              </PressableScale>
            </View>
          ) : null}

          {items.map((c) => (
            <Link key={c.conversation_id} href={`/chat/${c.conversation_id}`} asChild>
              <PressableScale className="mb-2 flex-row items-center gap-3 rounded-xl border border-hairline bg-surface p-4 hover:border-hairline">
                <MessageSquare size={16} color="var(--c-text-faint)" />
                <View className="flex-1">
                  <Text className="text-body font-semibold text-primary" numberOfLines={1}>
                    {c.title || 'Untitled conversation'}
                  </Text>
                  <Text className="text-xs text-faint">{c.message_count} messages</Text>
                </View>
              </PressableScale>
            </Link>
          ))}
        </ScreenView>
      </ScrollView>
    </View>
  );
}
