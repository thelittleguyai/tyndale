/** Scripted opener for an EMPTY freeform conversation (Brock 2026-08-22, item 4).
 *
 *  A client-rendered assistant bubble + four choice chips — no LLM call, nothing persisted
 *  until the user replies; a tapped chip (or typed text) becomes the first user turn and the
 *  thread then flows normally. Copy comes from the orchestration-script registry via the
 *  'chat' copy surface (keys freeform_opener / freeform_opener_chips — PROPOSED for Brock,
 *  interim seed); the fallbacks below are that same seed so the opener renders offline. */

import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { getSurfaceCopy } from '../../lib/api-client';

export const OPENER_FALLBACK = 'What can I help you with today?';
export const OPENER_CHIPS_FALLBACK =
  'Understand a bill · Check if a bill is correct · Think I\'m overcharged · Something else';

/** The registry stores the four chips as ONE string separated by " · ". */
export function splitChips(value: string | null | undefined): string[] {
  return (value || OPENER_CHIPS_FALLBACK)
    .split('·')
    .map((c) => c.trim())
    .filter(Boolean)
    .slice(0, 4);
}

export function FreeformOpener({
  onChip,
  copy,
  conversationId,
}: {
  onChip: (text: string) => void;
  /** Inject copy (tests); omitted → fetched from the 'chat' surface with fallbacks. */
  copy?: { opener?: string | null; opener_chips?: string | null };
  /** When given, a quiet "upload it" link under the chips opens a new case with the
   *  conversation preserved — one tap from the first screen, no second chip row. */
  conversationId?: string;
}) {
  const router = useRouter();
  const [fetched, setFetched] = useState<{ opener?: string | null; opener_chips?: string | null }>({});
  useEffect(() => {
    if (copy) return;
    let alive = true;
    getSurfaceCopy('chat')
      .then((c) => alive && setFetched(c))
      .catch(() => {/* fallbacks render */});
    return () => {
      alive = false;
    };
  }, [copy]);
  const c = copy ?? fetched;
  const opener = c.opener || OPENER_FALLBACK;
  const chips = splitChips(c.opener_chips);

  return (
    <View className="mb-3 items-start" testID="freeform-opener">
      <View className="max-w-[92%] rounded-2xl rounded-tl-sm border border-hairline bg-surface px-3.5 py-3">
        <Text className="text-body leading-6 text-primary">{opener}</Text>
      </View>
      <View className="mt-2 ml-1 flex-row flex-wrap gap-2">
        {chips.map((chip) => (
          <Pressable
            key={chip}
            onPress={() => onChip(chip)}
            accessibilityRole="button"
            className="min-h-[36px] justify-center rounded-full border border-accent bg-surface px-4 py-1.5 hover:bg-accent-tint active:opacity-70"
          >
            <Text className="text-sm font-semibold text-accent">{chip}</Text>
          </Pressable>
        ))}
      </View>
      {conversationId ? (
        <Pressable
          onPress={() =>
            router.push({ pathname: '/upload', params: { fromConversation: conversationId } })
          }
          accessibilityRole="button"
          testID="opener-upload"
          className="ml-1 mt-3 min-h-[44px] justify-center self-start active:opacity-70"
        >
          <Text className="text-sm font-semibold text-accent">Have a bill ready? Upload it →</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
