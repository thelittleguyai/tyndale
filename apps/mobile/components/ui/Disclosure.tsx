/**
 * Disclosure — a collapsed-by-default expandable (redesign §2). Long explainers (the italic "what
 * this usually looks like", a finding's "what to do") hide behind a link-styled summary so cards
 * stay scannable instead of becoming text walls.
 */
import { type ReactNode, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ChevronDown, ChevronUp } from 'lucide-react-native';

export function Disclosure({
  summary,
  children,
  defaultOpen = false,
}: {
  /** Link-styled summary, e.g. "Show what this usually looks like". */
  summary: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <View>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        className="min-h-[44px] flex-row items-center gap-1 active:opacity-70"
      >
        <Text className="text-caption font-medium text-accent">{summary}</Text>
        {open ? (
          <ChevronUp size={14} color="var(--c-accent)" />
        ) : (
          <ChevronDown size={14} color="var(--c-accent)" />
        )}
      </Pressable>
      {open ? <View className="pb-1 pt-1">{children}</View> : null}
    </View>
  );
}
