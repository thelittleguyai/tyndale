/**
 * ThemeToggle — a Light / Dark / System segmented control (redesign §3, Settings). Wired to the
 * theme controller: selecting an option applies it immediately (NativeWind colorScheme) and
 * persists it. Built on the semantic tokens, so the control itself flips appearance with the mode
 * — immediate visual confirmation that the switch took.
 */
import { Pressable, Text, View } from 'react-native';

import type { ThemeMode } from '../../theme/tokens';
import { useThemeController } from '../../theme/useTheme';

const OPTIONS: { mode: ThemeMode; label: string }[] = [
  { mode: 'light', label: 'Light' },
  { mode: 'dark', label: 'Dark' },
  { mode: 'system', label: 'System' },
];

export function ThemeToggle() {
  const { mode, setMode } = useThemeController();
  return (
    <View className="flex-row gap-1 rounded-control bg-inset p-1">
      {OPTIONS.map((o) => {
        const active = mode === o.mode;
        return (
          <Pressable
            key={o.mode}
            onPress={() => setMode(o.mode)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            className={`min-h-[44px] flex-1 items-center justify-center rounded-control ${
              active ? 'bg-accent' : 'active:bg-surface'
            }`}
          >
            <Text className={`text-body font-medium ${active ? 'text-on-accent' : 'text-secondary'}`}>
              {o.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
