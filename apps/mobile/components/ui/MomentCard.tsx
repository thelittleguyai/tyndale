/**
 * MomentCard — the designed "moment" surface (redesign §2). Its own token slots (moment.bg /
 * border / emphasis / text), 16r, full-width — deliberately distinct from ordinary cards in BOTH
 * modes. Used ONLY for the three-number reveal, the first-case unlock, and the two continuous-
 * journey beats. Never for routine content.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

export function MomentCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <View className={`w-full rounded-moment border border-moment-border bg-moment-bg p-5 ${className}`}>
      {children}
    </View>
  );
}
