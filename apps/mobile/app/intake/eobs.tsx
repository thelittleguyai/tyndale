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

export default function EobsStep() {
  const { caseId, state, loading, error } = useWizard();
  const [count, setCount] = useState(state?.captured_data.eobs_count ?? 0);
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;

  const onUploaded = (docs: UploadedDoc[]) => setCount((c) => c + docs.length);

  const advance = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await intakeSkipStep('eobs', caseId);
      goToStep('visit-context');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="eobs"
      title="Do you have an EOB from your insurer?"
      subtitle="An EOB — 'Explanation of Benefits' — is the summary your insurer mails or posts after a visit. It's not a bill. If you only have bills, that's okay; the analysis is just a bit more limited."
      why="Your EOB tells me what your insurer says they paid and what they say you owe. I compare that against my own calculation — that's how I catch insurer mistakes."
      example="An 'Explanation of Benefits' from your insurer — says 'This is not a bill' at the top"
      onContinue={advance}
      busy={busy}
      error={error ?? saveErr}
      skippable
      onSkip={advance}
    >
      {caseId ? (
        <UploadField caseId={caseId} label="Add your EOB(s)" onUploaded={onUploaded} />
      ) : null}
      {count > 0 ? (
        <Text className="mt-3 text-sm text-accent">
          {count} EOB{count === 1 ? '' : 's'} added — now I can audit both sides.
        </Text>
      ) : null}
    </WizardShell>
  );
}
