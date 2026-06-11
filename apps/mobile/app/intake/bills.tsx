import { useState } from 'react';
import { Text } from 'react-native';

import { type UploadedDoc, intakeSkipStep } from '../../lib/api-client';
import {
  SAVE_ERROR_MESSAGE,
  UploadField,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

export default function BillsStep() {
  const { caseId, state, loading, error } = useWizard();
  const [count, setCount] = useState(state?.captured_data.bills_count ?? 0);
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;

  const onUploaded = (docs: UploadedDoc[]) => setCount((c) => c + docs.length);

  const advance = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await intakeSkipStep('bills', caseId);
      goToStep('eobs');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="bills"
      title="Upload any bills you've received for this visit."
      subtitle="Multiple bills are normal — surgery often comes with separate bills from the hospital, the surgeon, and the anesthesiologist. Add as many as you have."
      why="The bill is what I audit line by line. You can finish setup without one, but I can't run the analysis until at least one bill is here."
      example="A hospital or provider statement showing charges and an amount due"
      onContinue={advance}
      continueLabel={count > 0 ? 'Continue' : 'Continue without a bill for now'}
      busy={busy}
      error={error ?? saveErr}
    >
      {caseId ? (
        <UploadField caseId={caseId} label="Add your medical bill(s)" onUploaded={onUploaded} />
      ) : null}
      {count > 0 ? (
        <Text className="mt-3 text-sm text-sage">
          {count} bill{count === 1 ? '' : 's'} added — that's enough to run the analysis later.
        </Text>
      ) : null}
    </WizardShell>
  );
}
