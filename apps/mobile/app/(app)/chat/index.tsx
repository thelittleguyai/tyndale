/** Freeform "Ask Tyndale" conversation list (Phase CO-10). */

import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { Link, useRouter } from 'expo-router';
import { ChevronLeft, MessageSquare, Plus } from 'lucide-react-native';

import type { Conversation } from '@tyndale/shared';

import { createConversation, listConversations } from '../../../lib/api-client';
import { PressableScale } from '../../../components/ui/PressableScale';
import { ScreenView } from '../../../components/ui/Screen';

export default function ChatListScreen() {
  const router = useRouter();
  const [items, setItems] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

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
    <View className="flex-1 bg-navy-deep">
      <View className="flex-row items-center justify-between border-b border-white/10 bg-navy-soft px-4 py-3">
        <Link href="/" asChild>
          <Pressable className="min-h-[44px] flex-row items-center gap-1 active:opacity-70">
            <ChevronLeft size={18} color="rgba(255,255,255,0.7)" />
            <Text className="text-sm text-white/70 hover:text-white/90">Home</Text>
          </Pressable>
        </Link>
        <Text className="text-base font-bold text-white">Ask Tyndale</Text>
        <PressableScale
          onPress={start}
          className="min-h-[44px] flex-row items-center gap-1 rounded-full bg-sage px-3 py-1.5 hover:bg-sage-deep"
        >
          <Plus size={14} color="#0A1E1C" />
          <Text className="text-xs font-bold text-ink">New</Text>
        </PressableScale>
      </View>

      <ScrollView className="flex-1 px-4" contentContainerStyle={{ paddingVertical: 16 }}>
        <ScreenView>
          {loading ? <ActivityIndicator color="#fff" className="mt-8" /> : null}

          {!loading && items.length === 0 ? (
            <View className="mt-6 rounded-2xl border border-white/10 bg-navy-soft p-5 shadow-card">
              <Text className="text-sm leading-6 text-white/70">
                Ask anything about medical billing. I can help with insurance terms, billing
                codes, your rights, appeals processes, and more. For specific bill analysis,
                upload your documents in a case file.
              </Text>
              <PressableScale
                onPress={start}
                className="mt-4 min-h-[44px] justify-center self-start rounded-xl bg-sage px-4 py-2.5 hover:bg-sage-deep"
              >
                <Text className="text-sm font-bold text-ink">Start a conversation</Text>
              </PressableScale>
            </View>
          ) : null}

          {items.map((c) => (
            <Link key={c.conversation_id} href={`/chat/${c.conversation_id}`} asChild>
              <PressableScale className="mb-2 flex-row items-center gap-3 rounded-xl border border-white/10 bg-navy-soft p-4 hover:border-white/25">
                <MessageSquare size={16} color="rgba(255,255,255,0.5)" />
                <View className="flex-1">
                  <Text className="text-sm font-semibold text-white/90" numberOfLines={1}>
                    {c.title || 'Untitled conversation'}
                  </Text>
                  <Text className="text-xs text-white/40">{c.message_count} messages</Text>
                </View>
              </PressableScale>
            </Link>
          ))}
        </ScreenView>
      </ScrollView>
    </View>
  );
}
