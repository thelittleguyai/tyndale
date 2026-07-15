/**
 * MetricCard — caption label / 22px number / micro qualifier, with an optional 4px progress track
 * (redesign §2). The uniform coverage + outcome tiles on the Record/dashboard use this.
 */
import { Text, View } from 'react-native';

import { Card } from './Card';

type Tone = 'accent' | 'success' | 'warning' | 'danger';

const FILL: Record<Tone, string> = {
  accent: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
};

// Literal map — NativeWind extracts classes statically, so a `text-${tone}` template would be
// dropped. Keep these spelled out.
const VALUE_TONE: Record<Tone, string> = {
  accent: 'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
};

function ProgressTrack({ value, tone }: { value: number; tone: Tone }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <View className="mt-3 h-1 overflow-hidden rounded-full bg-inset">
      <View className={`h-1 rounded-full ${FILL[tone]}`} style={{ width: `${pct}%` }} />
    </View>
  );
}

export function MetricCard({
  label,
  value,
  qualifier,
  progress,
  tone = 'accent',
  valueTone,
}: {
  label: string;
  value: string;
  qualifier?: string;
  /** 0..1 — renders the 4px track when provided. */
  progress?: number;
  tone?: Tone;
  /** Optionally color the number (e.g. recovered in success). Defaults to primary text. */
  valueTone?: Tone;
}) {
  const numberClass = valueTone ? VALUE_TONE[valueTone] : 'text-primary';
  return (
    <Card className="flex-1">
      <Text className="text-caption text-secondary">{label}</Text>
      <Text className={`mt-1 text-[22px] font-medium leading-7 ${numberClass}`}>{value}</Text>
      {qualifier ? <Text className="text-micro text-faint">{qualifier}</Text> : null}
      {progress != null ? <ProgressTrack value={progress} tone={tone} /> : null}
    </Card>
  );
}
