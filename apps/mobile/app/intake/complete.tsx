import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';

import { type IntakeCompletionSummary, completeIntake, getIntakeState } from '../../lib/api-client';
import { WizardLoading, WizardShell } from '../../lib/intake-ui';

export default function CompleteStep() {
  const [summary, setSummary] = useState<IntakeCompletionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const state = await getIntakeState();
        const s = await completeIntake(state.case_file_id);
        if (alive) setSummary(s);
      } catch {
        if (alive)
          setError(
            "We couldn't wrap things up just now — your answers are saved, so head to your dashboard and we'll pick it up from there.",
          );
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (loading) return <WizardLoading />;

  return (
    <WizardShell
      step="complete"
      title="Got it — you're all set."
      subtitle={summary?.summary}
      onContinue={() => router.replace('/' as never)}
      continueLabel="Take me to my dashboard"
      error={error}
    >
      {summary?.captured?.length ? (
        <View className="rounded-2xl border border-white/10 bg-navy-soft p-4">
          <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-sage">
            Here's what I have
          </Text>
          {summary.captured.map((c, i) => (
            <View key={i} className="mb-1 flex-row gap-2">
              <Text className="text-sage">✓</Text>
              <Text className="flex-1 text-sm leading-5 text-white/80">{c}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {summary?.missing_items?.length ? (
        <View className="mt-3 rounded-2xl border border-white/10 bg-navy-soft p-4">
          <Text className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber">
            When you have these, they'll unlock more
          </Text>
          {summary.missing_items.map((m, i) => (
            <View key={i} className="mb-1 flex-row gap-2">
              <Text className="text-amber">+</Text>
              <Text className="flex-1 text-sm leading-5 text-white/70">{m}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </WizardShell>
  );
}
