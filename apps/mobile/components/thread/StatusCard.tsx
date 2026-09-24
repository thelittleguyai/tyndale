/**
 * Chat-first live status card (DL-91, D2). ONE card, updated in place, with the four flow-stage
 * bars filling on REAL stage completion (each state is server-derived from case status). No
 * fabricated percentages: a bar is full only when its stage is done/failed; an active stage shows
 * an indeterminate working indicator, a pending stage an empty track.
 */
import { ActivityIndicator, Text, View } from 'react-native';

import type { StatusCardPayload, StatusCardVariant, ThreadStageState } from '@tyndale/shared';
import { useThemeColors } from '../../theme/useThemeColors';

function Bar({ state }: { state: ThreadStageState }) {
  // A bar fills (accent) only when its stage is genuinely done/failed — no fabricated progress
  // (D2). Active + pending both show an empty inset track; the row's spinner conveys activity.
  if (state === 'done') return <View className="h-1 rounded-full bg-accent" />;
  if (state === 'failed') return <View className="h-1 rounded-full bg-danger" />;
  if (state === 'waiting') return <View className="h-1 rounded-full bg-warning" />;
  return <View className="h-1 rounded-full bg-inset" />;
}

/** The variant a legacy card (no server variant) implies — the pre-2026-09-23 client rule. The
 *  server re-projects a stale card on the next read, so this is a one-render fallback. */
function legacyVariant(payload: StatusCardPayload): StatusCardVariant {
  const allDone = payload.stages.length > 0 && payload.stages.every((s) => s.state === 'done');
  if (allDone) return 'ready';
  if (!payload.paused && payload.stages.some((s) => s.state === 'active')) return 'working';
  return payload.terminal ? 'closed' : 'paused';
}

const LEGACY_HEADLINE: Partial<Record<StatusCardVariant, string>> = {
  ready: 'Audit ready',
  working: 'Working on your audit',
};

export function StatusCard({ payload }: { payload: StatusCardPayload }) {
  const tc = useThemeColors();
  // The header is the SERVER's decision (e2e re-test 2026-09-23 item 2): the client used to
  // infer "Audit ready" from "every bar done", and a system_error run marks every bar done —
  // so the card said "Audit ready ✓" above the apology. Now the variant comes with the card:
  // ready ✓, working (spinner), failed (!), waiting on documents; paused / closed have none.
  const variant = payload.variant ?? legacyVariant(payload);
  const headline =
    payload.variant !== undefined ? (payload.headline ?? null) : (LEGACY_HEADLINE[variant] ?? null);
  // Paused = waiting on the USER (verification / EOB confirm). A spinner would claim machine
  // work that isn't happening, so paused suppresses every ActivityIndicator (Brock 2026-08-22).
  const spinning = variant === 'working';
  return (
    <View
      className="my-2 w-full rounded-card border border-hairline bg-surface p-4"
      testID={`status-card-${variant}`}
    >
      {headline ? (
        <View className="mb-3 flex-row items-center justify-between">
          <Text className="text-body font-semibold text-primary">{headline}</Text>
          {variant === 'ready' ? (
            <Text className="text-body font-bold text-accent">✓</Text>
          ) : variant === 'working' ? (
            <ActivityIndicator size="small" color={tc.accent} />
          ) : variant === 'failed' ? (
            <Text className="text-body font-bold text-danger">!</Text>
          ) : variant === 'needs_documents' ? (
            <Text className="text-body font-bold text-warning">…</Text>
          ) : null}
        </View>
      ) : null}
      {payload.stages.map((s) => (
        <View key={s.key} className="mb-3 last:mb-0">
          <View className="mb-1.5 flex-row items-center justify-between">
            <Text
              className={`text-body ${s.state === 'pending' || s.state === 'skipped' ? 'text-faint' : 'text-primary'}`}
            >
              {s.label}
            </Text>
            {s.state === 'active' && spinning ? (
              <ActivityIndicator size="small" color={tc.accent} />
            ) : s.state === 'done' ? (
              <Text className="text-xs font-bold text-accent">✓</Text>
            ) : s.state === 'failed' ? (
              <Text className="text-xs font-bold text-danger">!</Text>
            ) : s.state === 'waiting' ? (
              <Text className="text-xs font-bold text-warning">…</Text>
            ) : s.state === 'skipped' ? (
              // could not run (e2e round 3 R6): no EOB → no insurer math to compare. Never ✓.
              <Text className="text-xs font-bold text-faint" testID={`stage-skipped-${s.key}`}>—</Text>
            ) : null}
          </View>
          <Bar state={s.state} />
        </View>
      ))}
    </View>
  );
}
