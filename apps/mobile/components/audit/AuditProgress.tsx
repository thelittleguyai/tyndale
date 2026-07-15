/**
 * Staged progress narrative shown while the audit pipeline runs.
 *
 * Maps the backend case-file status enum to a human checklist so the user
 * never sees a raw status string. Unknown statuses snap to the nearest
 * in-flight stage instead of leaking the enum.
 */

import { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { Check } from 'lucide-react-native';

const STAGES = [
  'Reading your bill',
  'Checking each charge',
  "Comparing with your insurer's math",
  'Writing your summary',
] as const;

/**
 * Backend statuses (see runtime case_files check constraint):
 * open | in_progress | encounter_verification_pending | encounter_verified |
 * audit_running | audit_complete | resolved | archived
 */
const STATUS_TO_STAGE: Record<string, number> = {
  open: 0,
  in_progress: 0,
  encounter_verification_pending: 1,
  encounter_verified: 2,
  audit_running: 2,
  audit_complete: 3,
  resolved: 3,
  archived: 3,
};

// Anything we don't recognize is almost certainly mid-pipeline.
const FALLBACK_STAGE = 2;

// After the audit has been running a while, optimistically advance to the
// "Writing your summary" stage so the checklist keeps feeling alive.
const SUMMARY_BUMP_MS = 12_000;

export function AuditProgress({ status }: { status: string }) {
  const baseStage = STATUS_TO_STAGE[status] ?? FALLBACK_STAGE;
  const [bumped, setBumped] = useState(false);

  useEffect(() => {
    if (baseStage !== 2) {
      setBumped(false);
      return;
    }
    const t = setTimeout(() => setBumped(true), SUMMARY_BUMP_MS);
    return () => clearTimeout(t);
  }, [baseStage]);

  const activeStage = baseStage === 2 && bumped ? 3 : baseStage;

  return (
    <View className="w-full max-w-2xl self-center px-6">
      <Text className="mb-1 text-xl font-bold text-primary">Checking your bill</Text>
      <Text className="mb-6 text-sm text-faint">This usually takes a minute or two.</Text>

      <View className="rounded-2xl border border-hairline bg-surface p-5">
        {STAGES.map((label, i) => {
          const done = i < activeStage;
          const active = i === activeStage;
          return (
            <View
              key={label}
              className={i < STAGES.length - 1 ? 'mb-4 flex-row items-center' : 'flex-row items-center'}
            >
              <View className="mr-3 h-6 w-6 items-center justify-center">
                {done ? (
                  <View className="h-6 w-6 items-center justify-center rounded-full bg-accent-tint">
                    <Check size={14} color="var(--c-accent)" strokeWidth={3} />
                  </View>
                ) : active ? (
                  <ActivityIndicator size="small" color="var(--c-accent)" />
                ) : (
                  <View className="h-2 w-2 rounded-full bg-inset" />
                )}
              </View>
              <Text
                className={
                  done
                    ? 'text-sm text-secondary'
                    : active
                      ? 'text-sm font-semibold text-primary'
                      : 'text-sm text-faint'
                }
              >
                {label}
              </Text>
            </View>
          );
        })}
      </View>

      <Text className="mt-5 text-center text-xs text-faint">
        Feel free to come back — we&rsquo;ll keep working.
      </Text>
    </View>
  );
}
