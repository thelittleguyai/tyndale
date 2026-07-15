import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import {
  type ConfirmationPrompt,
  type UploadedDoc,
  intakeExtractInsuranceCard,
  intakeManualEntry,
  intakeSkipStep,
} from '../../lib/api-client';
import {
  Field,
  SAVE_ERROR_MESSAGE,
  UploadField,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

export default function InsuranceCardStep() {
  const { caseId, loading, error } = useWizard();
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [confs, setConfs] = useState<ConfirmationPrompt[]>([]);
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [extractErr, setExtractErr] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;

  const onUploaded = async (uploaded: UploadedDoc[]) => {
    setDocs(uploaded);
    if (!caseId || !uploaded[0]) return;
    try {
      const ack = await intakeExtractInsuranceCard(uploaded[0].document_id, caseId);
      setConfs(ack.confirmations);
      // Seed corrections with the read values (user can edit the ones that are off).
      setCorrections(Object.fromEntries(ack.confirmations.map((c) => [c.field, c.read_value])));
    } catch {
      setExtractErr(
        "We couldn't read that photo — try another shot, or skip and type the details in next.",
      );
    }
  };

  const advance = async () => {
    if (!caseId) return;
    setBusy(true);
    setSaveErr(null);
    try {
      if (confs.length) {
        await intakeManualEntry('insurance-card', corrections, caseId);
      } else {
        await intakeSkipStep('insurance-card', caseId);
      }
      goToStep('coverage-regime-confirm');
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
      await intakeSkipStep('insurance-card', caseId);
      goToStep('coverage-regime-confirm');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="insurance-card"
      title="Let's start with your insurance card."
      subtitle="A photo of the front is enough. This is the fastest way to get your plan details — but if you don't have it handy, you can skip and type them in next."
      why="Your card has your member ID, group number, and plan name. These let me identify which plan rules apply to your bills."
      example="Front of a typical insurance card (member ID, group #, plan name)"
      onContinue={advance}
      continueLabel={docs.length ? 'Looks good — continue' : 'Continue'}
      busy={busy}
      error={error ?? saveErr ?? extractErr}
      skippable
      onSkip={onSkip}
    >
      {caseId ? (
        <UploadField caseId={caseId} label="Add a photo of your card" onUploaded={onUploaded} />
      ) : null}

      {docs.length ? (
        <Text className="mt-3 text-sm text-accent">
          Got it — {docs.length} image{docs.length === 1 ? '' : 's'} uploaded.
        </Text>
      ) : null}

      {confs.length ? (
        <View className="mt-4 rounded-2xl bg-warning-tint p-4">
          <Text className="mb-2 text-sm font-semibold text-warning">
            A couple of these were a little blurry — can you double-check?
          </Text>
          {confs.map((c) => (
            <View key={c.field} className="mb-3">
              <Text className="mb-1 text-sm text-secondary">{c.prompt}</Text>
              <Field
                label="Correct it if needed"
                value={corrections[c.field] ?? ''}
                onChangeText={(t) => setCorrections((m) => ({ ...m, [c.field]: t }))}
              />
            </View>
          ))}
        </View>
      ) : null}
    </WizardShell>
  );
}
