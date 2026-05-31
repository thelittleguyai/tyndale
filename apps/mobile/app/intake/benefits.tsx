import { useState } from 'react';
import { Text } from 'react-native';

import { intakeManualEntry, intakeSkipStep } from '../../lib/api-client';
import {
  Field,
  UploadField,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

const num = (s: string): number | undefined => {
  const n = parseFloat(s.replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) ? n : undefined;
};

export default function BenefitsStep() {
  const { caseId, loading, error } = useWizard();
  const [ded, setDed] = useState('');
  const [oop, setOop] = useState('');
  const [coins, setCoins] = useState('');
  const [copayPcp, setCopayPcp] = useState('');
  const [copaySpec, setCopaySpec] = useState('');
  const [sbcUploaded, setSbcUploaded] = useState(false);
  const [busy, setBusy] = useState(false);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeManualEntry(
        'benefits',
        {
          deductible_amount: num(ded),
          oop_max_amount: num(oop),
          coinsurance_percent: num(coins),
          copay_pcp: num(copayPcp),
          copay_specialist: num(copaySpec),
        },
        caseId,
      );
      goToStep('deductible');
    } catch {
      setBusy(false);
    }
  };

  const onSkip = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeSkipStep('benefits', caseId);
      goToStep('deductible');
    } catch {
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="benefits"
      title="What does your plan cover?"
      subtitle="This is your Summary of Benefits (the 'SBC'). Upload it if you have it, or type in the key numbers — whatever's easier."
      why="With this, I can tell you if you're being charged correctly per your plan's rules. Without it, I can only check the bill itself for errors."
      example="A Summary of Benefits and Coverage (SBC) — usually a few pages from your insurer"
      onContinue={onContinue}
      busy={busy}
      error={error}
      skippable
      onSkip={onSkip}
    >
      {caseId ? (
        <UploadField
          caseId={caseId}
          label="Upload your Summary of Benefits (SBC)"
          onUploaded={() => setSbcUploaded(true)}
        />
      ) : null}
      {sbcUploaded ? (
        <Text className="mb-3 mt-3 text-sm text-sage">Got it — I'll read your SBC.</Text>
      ) : null}

      <Text className="mb-2 mt-4 text-xs uppercase tracking-widest text-white/45">
        Or enter the key numbers
      </Text>
      <Field label="Deductible (in-network)" value={ded} onChangeText={setDed} placeholder="$" keyboardType="numeric" />
      <Field label="Out-of-pocket max (in-network)" value={oop} onChangeText={setOop} placeholder="$" keyboardType="numeric" />
      <Field label="Coinsurance %" value={coins} onChangeText={setCoins} placeholder="e.g. 20" keyboardType="numeric" />
      <Field label="Primary-care copay" value={copayPcp} onChangeText={setCopayPcp} placeholder="$" keyboardType="numeric" />
      <Field label="Specialist copay" value={copaySpec} onChangeText={setCopaySpec} placeholder="$" keyboardType="numeric" />
    </WizardShell>
  );
}
