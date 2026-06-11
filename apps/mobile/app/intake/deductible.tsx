import { useState } from 'react';

import { intakeManualEntry, intakeSkipStep } from '../../lib/api-client';
import {
  Field,
  SAVE_ERROR_MESSAGE,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

const num = (s: string): number | undefined => {
  const n = parseFloat(s.replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) ? n : undefined;
};

export default function DeductibleStep() {
  const { caseId, state, loading, error } = useWizard();
  const cov = (state?.captured_data.coverage ?? {}) as Record<string, number>;
  const [total, setTotal] = useState(cov.deductible_amount ? String(cov.deductible_amount) : '');
  const [met, setMet] = useState('');
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await intakeManualEntry(
        'deductible',
        { deductible_total: num(total), deductible_met: num(met) },
        caseId,
      );
      goToStep('oop-max');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  const onSkip = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await intakeSkipStep('deductible', caseId);
      goToStep('oop-max');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="deductible"
      title="How much of your deductible have you met this year?"
      subtitle="A deductible is what you pay before your insurance starts chipping in. No need to be exact — a close number is fine."
      why="Knowing where you are against your deductible lets me check whether your insurer applied it correctly to this bill."
      example="Your insurer's app or portal shows 'plan-year spending' or 'deductible status'. Some EOBs show a running total at the bottom."
      onContinue={onContinue}
      busy={busy}
      error={error ?? saveErr}
      skippable
      onSkip={onSkip}
    >
      <Field label="Your total deductible" value={total} onChangeText={setTotal} placeholder="$" keyboardType="numeric" />
      <Field label="How much you've met so far" value={met} onChangeText={setMet} placeholder="$" keyboardType="numeric" />
    </WizardShell>
  );
}
