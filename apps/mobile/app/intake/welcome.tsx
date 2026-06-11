import { intakeSkipStep } from '../../lib/api-client';
import { WizardLoading, WizardShell, goToStep, useWizard } from '../../lib/intake-ui';

export default function WelcomeStep() {
  const { caseId, loading, error } = useWizard();

  if (loading) return <WizardLoading />;

  const onContinue = () => {
    // Navigate right away — the first tap should feel instant. Marking the step
    // complete happens in the background; the next screen re-syncs intake state
    // on mount, so nothing depends on this call finishing first.
    goToStep('insurance-card');
    if (caseId) void intakeSkipStep('welcome', caseId).catch(() => undefined);
  };

  return (
    <WizardShell
      step="welcome"
      title="Let's get your bills and benefits set up."
      subtitle="We'll go one thing at a time, and you can stop whenever you want — we'll save your progress. There are no wrong answers here; share what you have and we'll work with it."
      onContinue={onContinue}
      continueLabel="Let's start"
      error={error}
    />
  );
}
