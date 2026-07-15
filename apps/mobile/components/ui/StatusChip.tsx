/**
 * StatusChip — a tint pill (redesign §2). One shape for status across the app: success / warning /
 * danger / neutral, each a tinted background with its on-tint text stop.
 */
import { Text, View } from 'react-native';

export type ChipTone = 'success' | 'warning' | 'danger' | 'neutral';

const TONE: Record<ChipTone, string> = {
  success: 'bg-success-tint',
  warning: 'bg-warning-tint',
  danger: 'bg-danger-tint',
  neutral: 'bg-inset',
};

const TEXT: Record<ChipTone, string> = {
  success: 'text-success-on-tint',
  warning: 'text-warning-on-tint',
  danger: 'text-danger-on-tint',
  neutral: 'text-secondary',
};

export function StatusChip({ label, tone = 'neutral' }: { label: string; tone?: ChipTone }) {
  return (
    <View className={`self-start rounded-full px-2.5 py-1 ${TONE[tone]}`}>
      <Text className={`text-caption font-medium ${TEXT[tone]}`}>{label}</Text>
    </View>
  );
}
