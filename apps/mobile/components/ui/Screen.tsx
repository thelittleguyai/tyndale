/**
 * Max-width screen wrappers so content doesn't stretch edge-to-edge on wide
 * web viewports. Mirrors the existing pattern in components/chat/ChatThread
 * (`w-full max-w-3xl self-center`).
 *
 * - <Screen>      ScrollView-based: full-bleed scroll surface (background +
 *                 contentContainer padding span the viewport) with children
 *                 constrained to a centered column.
 * - <ScreenView>  Plain View version, for wrapping a section inside an
 *                 existing scroll/flex layout.
 *
 * Default column is max-w-2xl; pass `wide` for max-w-5xl (dashboard grid).
 */

import { ScrollView, View, type ScrollViewProps, type ViewProps } from 'react-native';

const column = (wide: boolean | undefined, extra?: string) =>
  `w-full ${wide ? 'max-w-5xl' : 'max-w-2xl'} self-center ${extra ?? ''}`;

export type ScreenProps = ScrollViewProps & {
  /** Wider column (max-w-5xl) for grid-style screens like the dashboard. */
  wide?: boolean;
  /** Extra classes for the inner constrained column. */
  contentClassName?: string;
};

export function Screen({ wide, contentClassName, children, ...scrollProps }: ScreenProps) {
  return (
    <ScrollView {...scrollProps}>
      <View className={column(wide, contentClassName)}>{children}</View>
    </ScrollView>
  );
}

export type ScreenViewProps = ViewProps & {
  wide?: boolean;
  className?: string;
};

export function ScreenView({ wide, className, children, ...viewProps }: ScreenViewProps) {
  return (
    <View className={column(wide, className)} {...viewProps}>
      {children}
    </View>
  );
}
