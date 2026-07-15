/**
 * ListRow — icon + two-line + trailing (redesign §2). The Record row (provider / visit date /
 * outcome / trailing chip) and the gameplan steps use this. 44px minimum touch target when
 * pressable.
 */
import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';
import { ChevronRight } from 'lucide-react-native';

export function ListRow({
  leading,
  title,
  subtitle,
  meta,
  trailing,
  onPress,
  showChevron = false,
}: {
  leading?: ReactNode;
  title: string;
  subtitle?: string;
  /** A third faint line (e.g. a deadline). */
  meta?: string;
  /** Trailing content — typically a StatusChip. */
  trailing?: ReactNode;
  onPress?: () => void;
  showChevron?: boolean;
}) {
  const Wrapper: typeof Pressable | typeof View = onPress ? Pressable : View;
  return (
    <Wrapper
      onPress={onPress}
      accessibilityRole={onPress ? 'button' : undefined}
      className="min-h-[44px] flex-row items-center gap-3 rounded-card border border-hairline bg-surface p-4 active:bg-inset"
    >
      {leading}
      <View className="flex-1">
        <Text className="text-heading text-primary" numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? (
          <Text className="mt-0.5 text-caption text-secondary" numberOfLines={1}>
            {subtitle}
          </Text>
        ) : null}
        {meta ? (
          <Text className="mt-0.5 text-micro text-faint" numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </View>
      {trailing}
      {showChevron ? <ChevronRight size={18} color="var(--c-text-faint)" /> : null}
    </Wrapper>
  );
}
