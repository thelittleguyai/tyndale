/**
 * The segmented intake progress bar (doc 40 §A8) — one segment per group, under the header on
 * every intake screen. Everything it shows comes from the server's planner: which segments are
 * filled (including ones HELD by the persisted high-water mark — the bar never regresses), the
 * line ("1 of 7 — nice start"; never a bare "Step N of M"; nothing at all before the first
 * landing), and the one-line note when a reclassified document no longer backs a segment.
 */
import { Text, View } from 'react-native';

import type { IntakeProgress } from '@tyndale/shared';

export function IntakeProgressBar({ progress }: { progress: IntakeProgress }) {
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={progress.line ?? undefined}
      accessibilityValue={{ min: 0, max: progress.total, now: progress.filled }}
      testID="intake-progress"
    >
      <View className="flex-row gap-1">
        {progress.segments.map((s) => (
          <View
            key={s.group}
            testID={`intake-segment-${s.group}`}
            accessibilityLabel={s.label ?? s.group}
            // an EMPTY segment outlines itself in the faint text colour (5.1:1 dark / 4.7:1 light on
            // the page): `bg-inset` alone was 1.02:1 on the dark page — invisible (2026-09-23 minor)
            className={`h-2 flex-1 rounded-full ${s.filled ? 'bg-accent' : 'border border-faint bg-inset'}`}
          />
        ))}
      </View>
      {progress.line ? (
        <Text className="mt-2 text-body text-secondary" testID="intake-progress-line">
          {progress.line}
        </Text>
      ) : null}
      {progress.note ? (
        <Text className="mt-1 text-body text-secondary" testID="intake-progress-note">
          {progress.note}
        </Text>
      ) : null}
    </View>
  );
}
