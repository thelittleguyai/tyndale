import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import type { CoverageRegime } from '@tyndale/shared';

import { intakeConfirmRegime, intakeSkipStep } from '../../lib/api-client';
import {
  SAVE_ERROR_MESSAGE,
  WizardLoading,
  WizardShell,
  goToStep,
  useWizard,
} from '../../lib/intake-ui';

// Plain-language labels for the seven coverage regimes (DL-82). The user confirms
// which one applies so their bills are audited under the right population's rules —
// never commercial-by-analogy.
const REGIME_OPTIONS: { value: CoverageRegime; label: string; hint: string }[] = [
  { value: 'commercial', label: 'Commercial or employer insurance', hint: 'A plan through work or one you bought — PPO, HMO, EPO' },
  { value: 'medicare_traditional', label: 'Original Medicare', hint: 'Parts A & B, the red-white-and-blue card' },
  { value: 'medicare_advantage', label: 'Medicare Advantage', hint: 'A private Medicare plan (Part C) — often named for an insurer' },
  { value: 'medicaid', label: 'Medicaid', hint: 'State coverage, including a Medicaid managed-care plan' },
  { value: 'dual_qmb', label: 'Both Medicare and Medicaid', hint: 'Dual-eligible / QMB — you have both' },
  { value: 'tricare_va', label: 'TRICARE, VA, or CHAMPVA', hint: 'Military or veterans coverage' },
  { value: 'self_pay', label: "I don't have insurance", hint: "You're paying for this yourself" },
];

export default function CoverageRegimeConfirmStep() {
  const { state, caseId, loading, error } = useWizard();
  const detection = state?.captured_data.regime_detection ?? null;
  const [selected, setSelected] = useState<CoverageRegime | ''>('');
  const [busy, setBusy] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  // Preselect the detected candidate once it loads (the user can change it).
  useEffect(() => {
    if (detection?.candidate) setSelected((s) => s || detection.candidate!);
  }, [detection?.candidate]);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId || !selected) return;
    setBusy(true);
    setSaveErr(null);
    try {
      await intakeConfirmRegime(selected, caseId);
      goToStep('coverage-details');
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
      await intakeSkipStep('coverage-regime-confirm', caseId);
      goToStep('coverage-details');
    } catch {
      setSaveErr(SAVE_ERROR_MESSAGE);
      setBusy(false);
    }
  };

  // A soft hint when detection had a confident-enough guess to lead with.
  const detectedLabel =
    detection?.candidate &&
    REGIME_OPTIONS.find((o) => o.value === detection.candidate)?.label;

  return (
    <WizardShell
      step="coverage-regime-confirm"
      title="How are you covered?"
      subtitle={
        detectedLabel
          ? `From your card, this looks like ${detectedLabel}. Tap to confirm or change it.`
          : "Let's confirm your coverage type so I apply the right billing rules."
      }
      why="Commercial, Medicare, Medicaid, and military coverage each follow different billing and appeal rules. Getting this right means the numbers and the next steps I give you are accurate."
      onContinue={onContinue}
      continueLabel={selected ? 'Confirm' : 'Choose one to continue'}
      busy={busy}
      error={error ?? saveErr}
      skippable
      onSkip={onSkip}
    >
      <View className="gap-2">
        {REGIME_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <Pressable
              key={opt.value}
              onPress={() => setSelected(opt.value)}
              className={`rounded-2xl border p-4 ${
                active ? 'border-sage bg-sage/10' : 'border-white/15 bg-navy-soft'
              }`}
            >
              <Text className={`text-base font-semibold ${active ? 'text-sage' : 'text-white'}`}>
                {opt.label}
              </Text>
              <Text className="mt-0.5 text-[13px] leading-5 text-white/60">{opt.hint}</Text>
            </Pressable>
          );
        })}
      </View>
    </WizardShell>
  );
}
