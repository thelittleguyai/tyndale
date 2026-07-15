/** Small clickable badge with a (truncated) source title → opens the detail modal. */

import { BookOpen } from 'lucide-react-native';
import { Pressable, Text } from 'react-native';

import type { ChatCitation } from '@tyndale/shared';

function label(c: ChatCitation): string {
  const raw = c.title || c.source_id || c.url || 'Source';
  return raw.length > 30 ? `${raw.slice(0, 29)}…` : raw;
}

export function CitationChip({
  citation,
  onPress,
}: {
  citation: ChatCitation;
  onPress: (c: ChatCitation) => void;
}) {
  return (
    <Pressable
      onPress={() => onPress(citation)}
      accessibilityRole="button"
      hitSlop={10}
      className="flex-row items-center gap-1 rounded-full border border-accent bg-accent-tint px-2 py-1"
    >
      <BookOpen size={11} color="var(--c-accent)" />
      <Text className="text-[11px] text-accent">{label(citation)}</Text>
    </Pressable>
  );
}
