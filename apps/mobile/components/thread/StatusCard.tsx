/**
 * Chat-first live status card (DL-91, D2). ONE card, updated in place, with the four flow-stage
 * bars filling on REAL stage completion (each state is server-derived from case status). No
 * fabricated percentages: a bar is full only when its stage is done/failed; an active stage shows
 * an indeterminate working indicator, a pending stage an empty track.
 */
import { ActivityIndicator, Text, View } from 'react-native';

import type { StatusCardPayload, ThreadStageState } from '@tyndale/shared';

function Bar({ state }: { state: ThreadStageState }) {
  if (state === 'done') return <View className="h-1.5 rounded-full bg-accent" />;
  if (state === 'failed') return <View className="h-1.5 rounded-full bg-danger" />;
  if (state === 'active') return <View className="h-1.5 rounded-full bg-surface-raised/60" />; // indeterminate
  return <View className="h-1.5 rounded-full bg-inset" />; // pending — empty track
}

export function StatusCard({ payload }: { payload: StatusCardPayload }) {
  return (
    <View className="my-2 w-full rounded-2xl border border-hairline bg-surface p-4">
      {payload.stages.map((s) => (
        <View key={s.key} className="mb-3 last:mb-0">
          <View className="mb-1.5 flex-row items-center justify-between">
            <Text
              className={`text-sm ${s.state === 'pending' ? 'text-faint' : 'text-primary'}`}
            >
              {s.label}
            </Text>
            {s.state === 'active' ? (
              <ActivityIndicator size="small" color="var(--c-accent)" />
            ) : s.state === 'done' ? (
              <Text className="text-xs font-bold text-accent">✓</Text>
            ) : s.state === 'failed' ? (
              <Text className="text-xs font-bold text-danger">!</Text>
            ) : null}
          </View>
          <Bar state={s.state} />
        </View>
      ))}
    </View>
  );
}
