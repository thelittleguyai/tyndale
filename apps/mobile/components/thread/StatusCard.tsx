/**
 * Chat-first live status card (DL-91, D2). ONE card, updated in place, with the four flow-stage
 * bars filling on REAL stage completion (each state is server-derived from case status). No
 * fabricated percentages: a bar is full only when its stage is done/failed; an active stage shows
 * an indeterminate working indicator, a pending stage an empty track.
 */
import { ActivityIndicator, Text, View } from 'react-native';

import type { StatusCardPayload, ThreadStageState } from '@tyndale/shared';

function Bar({ state }: { state: ThreadStageState }) {
  // A bar fills (accent) only when its stage is genuinely done/failed — no fabricated progress
  // (D2). Active + pending both show an empty inset track; the row's spinner conveys activity.
  if (state === 'done') return <View className="h-1 rounded-full bg-accent" />;
  if (state === 'failed') return <View className="h-1 rounded-full bg-danger" />;
  return <View className="h-1 rounded-full bg-inset" />;
}

export function StatusCard({ payload }: { payload: StatusCardPayload }) {
  // L1 (round-2) — a state header over the bars. Only the two states the prototype authors:
  // "Working on your audit" while anything is genuinely active, "Audit ready" when all four
  // stages are done. A failed/incomplete terminal gets NO header — the rows carry that truth,
  // and inventing a third header state here would be copy nobody wrote.
  const allDone = payload.stages.length > 0 && payload.stages.every((s) => s.state === 'done');
  // Paused = waiting on the USER (verification / EOB confirm). A spinner would claim machine
  // work that isn't happening, so paused suppresses the working header and every
  // ActivityIndicator — same words, still no third header state (Brock 2026-08-22).
  const anyActive = !payload.paused && payload.stages.some((s) => s.state === 'active');
  return (
    <View className="my-2 w-full rounded-card border border-hairline bg-surface p-4">
      {allDone ? (
        <View className="mb-3 flex-row items-center justify-between">
          <Text className="text-body font-semibold text-primary">Audit ready</Text>
          <Text className="text-body font-bold text-accent">✓</Text>
        </View>
      ) : anyActive ? (
        <View className="mb-3 flex-row items-center justify-between">
          <Text className="text-body font-semibold text-primary">Working on your audit</Text>
          <ActivityIndicator size="small" color="var(--c-accent)" />
        </View>
      ) : null}
      {payload.stages.map((s) => (
        <View key={s.key} className="mb-3 last:mb-0">
          <View className="mb-1.5 flex-row items-center justify-between">
            <Text
              className={`text-body ${s.state === 'pending' ? 'text-faint' : 'text-primary'}`}
            >
              {s.label}
            </Text>
            {s.state === 'active' && !payload.paused ? (
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
