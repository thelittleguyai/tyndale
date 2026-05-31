import { useState } from 'react';

import { intakeSkipStep } from '../../lib/api-client';
import { WizardLoading, WizardShell, goToStep, useWizard } from '../../lib/intake-ui';

export default function WelcomeStep() {
  const { caseId, loading, error } = useWizard();
  const [busy, setBusy] = useState(false);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeSkipStep('welcome', caseId);
      goToStep('insurance-card');
    } catch {
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="welcome"
      title="Let's get your bills and benefits set up."
      subtitle="We'll go one thing at a time, and you can stop whenever you want — we'll save your progress. There are no wrong answers here; share what you have and we'll work with it."
      onContinue={onContinue}
      continueLabel="Let's start"
      busy={busy}
      error={error}
    />
  );
}
