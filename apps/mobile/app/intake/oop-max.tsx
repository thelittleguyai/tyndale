import { useState } from 'react';

import { intakeManualEntry, intakeSkipStep } from '../../lib/api-client';
import { Field, WizardLoading, WizardShell, goToStep, useWizard } from '../../lib/intake-ui';

const num = (s: string): number | undefined => {
  const n = parseFloat(s.replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) ? n : undefined;
};

export default function OopMaxStep() {
  const { caseId, state, loading, error } = useWizard();
  const cov = (state?.captured_data.coverage ?? {}) as Record<string, number>;
  const [total, setTotal] = useState(cov.oop_max_amount ? String(cov.oop_max_amount) : '');
  const [met, setMet] = useState('');
  const [busy, setBusy] = useState(false);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeManualEntry(
        'oop-max',
        { oop_max_total: num(total), oop_max_met: num(met) },
        caseId,
      );
      goToStep('bills');
    } catch {
      setBusy(false);
    }
  };

  const onSkip = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeSkipStep('oop-max', caseId);
      goToStep('bills');
    } catch {
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="oop-max"
      title="And your out-of-pocket maximum?"
      subtitle="This is the most you'll pay in a year before your plan covers 100%. Same idea as the last screen — a close number is fine, and you can skip it."
      why="Once you hit your out-of-pocket max, you shouldn't owe anything more. I'll flag it if a bill ignores that."
      onContinue={onContinue}
      busy={busy}
      error={error}
      skippable
      onSkip={onSkip}
    >
      <Field label="Your out-of-pocket maximum" value={total} onChangeText={setTotal} placeholder="$" keyboardType="numeric" />
      <Field label="How much you've met so far" value={met} onChangeText={setMet} placeholder="$" keyboardType="numeric" />
    </WizardShell>
  );
}
