import { useState } from 'react';
import { Text, TextInput, View } from 'react-native';

import { setVisitContext } from '../../lib/api-client';
import { useThemeColors } from '../../theme/useThemeColors';
import {
  SAVE_ERROR_MESSAGE,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

const MAX = 500;

export default function VisitContextStep() {
  const tc = useThemeColors();
  const { caseId, state, loading, error } = useWizard();
  const [text, setText] = useState(state?.captured_data.visit_context ?? '');
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await setVisitContext(text.slice(0, MAX), caseId);
      goToStep('complete');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="visit-context"
      title="In your own words, what was this visit for?"
      subtitle="Don't worry about medical terms — just describe what happened. 'I went to the ER with chest pain' or 'I had a check-up and got blood work done.'"
      why="This helps me understand the context of your bill. The right care at the right level should cost a predictable amount; if there's a mismatch, I'll catch it."
      onContinue={onContinue}
      busy={busy}
      error={error ?? saveErr}
      skippable
      onSkip={onContinue}
    >
      <View>
        <TextInput
          value={text}
          onChangeText={(t) => setText(t.slice(0, MAX))}
          placeholder="Tell me what happened…"
          placeholderTextColor={tc.text.faint}
          multiline
          numberOfLines={5}
          className="min-h-[120px] rounded-xl border border-hairline bg-inset p-3 text-base leading-6 text-primary"
          textAlignVertical="top"
        />
        <Text className="mt-1 self-end text-xs text-faint">
          {text.length}/{MAX}
        </Text>
      </View>
    </WizardShell>
  );
}
