/**
 * SectionHeader — a sentence-case caption in secondary text (redesign §2). Replaces the app's
 * ALL-CAPS low-contrast micro-labels; never uppercase.
 */
import { Text } from 'react-native';

export function SectionHeader({ children, className = '' }: { children: string; className?: string }) {
  return <Text className={`mb-3 mt-6 text-caption text-secondary ${className}`}>{children}</Text>;
}
