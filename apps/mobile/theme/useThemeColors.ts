/**
 * Resolved semantic colours for the CURRENT mode.
 *
 * Tailwind classes cover most styling, but some APIs need a literal colour string — lucide
 * icon `color=`, React Navigation `contentStyle`, `<Switch trackColor>`, `<ActivityIndicator>`.
 * Those used to hard-code hexes, which is exactly how the app drifted from the tokens (and how
 * a colour ended up defined in two places). Use this hook instead:
 *
 *     const c = useThemeColors();
 *     <CheckCircle2 color={c.success.base} />
 *
 * Values come from @tyndale/shared via theme/tokens — never define a hex in a component.
 */
import { useColorScheme } from 'nativewind';

import { dark, light, type SemanticColors } from './tokens';

export function useThemeColors(): SemanticColors {
  const { colorScheme } = useColorScheme();
  return colorScheme === 'dark' ? dark : light;
}

/** Non-hook access for module-scope constants (navigation options, etc.). */
export function themeColors(mode: 'light' | 'dark'): SemanticColors {
  return mode === 'dark' ? dark : light;
}
