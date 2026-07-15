/**
 * Card — the ONE card primitive (redesign §2). Surface fill + hairline + 12r. No more ad-hoc
 * grays or per-screen card styles; everything that needs a card uses this.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

export function Card({
  children,
  raised = false,
  className = '',
}: {
  children: ReactNode;
  raised?: boolean;
  className?: string;
}) {
  return (
    <View
      className={`rounded-card border border-hairline ${raised ? 'bg-surface-raised' : 'bg-surface'} p-4 ${className}`}
    >
      {children}
    </View>
  );
}
