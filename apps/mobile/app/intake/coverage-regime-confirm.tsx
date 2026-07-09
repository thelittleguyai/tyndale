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

// Plain-language labels for the 14 coverage regimes (Brock 2026-07-06, DL-90). The user confirms
// which one applies so their bills are audited under the right population's rules — never
// commercial-by-analogy. The detected candidate is preselected, so this is usually a one-tap
// confirm; the full list is here for correction.
const REGIME_OPTIONS: { value: CoverageRegime; label: string; hint: string }[] = [
  { value: 'state_regulated_commercial', label: 'Commercial or employer insurance', hint: 'A plan through work or one you bought — PPO, HMO, EPO' },
  { value: 'erisa_self_funded', label: 'Self-funded employer plan', hint: 'A large employer that pays claims itself (ERISA) — often says "self-funded" or "plan administrator"' },
  { value: 'medicare_traditional', label: 'Original Medicare', hint: 'Parts A & B, the red-white-and-blue card (incl. Medigap)' },
  { value: 'medicare_advantage', label: 'Medicare Advantage', hint: 'A private Medicare plan (Part C) — often named for an insurer' },
  { value: 'medicaid_ffs', label: 'Medicaid', hint: 'State coverage paid directly by the state' },
  { value: 'medicaid_mco', label: 'Medicaid managed-care plan', hint: 'State coverage through a private plan (Molina, Centene, etc.)' },
  { value: 'dual_eligible', label: 'Both Medicare and Medicaid', hint: 'Dual-eligible / QMB — you have both' },
  { value: 'tricare', label: 'TRICARE', hint: 'Active-duty or retired military coverage' },
  { value: 'va_champva', label: 'VA or CHAMPVA', hint: "Veterans' health care or CHAMPVA" },
  { value: 'fehb_pshb', label: 'Federal or postal employee plan', hint: 'FEHB or PSHB — a federal-government or USPS plan' },
  { value: 'nonfederal_governmental', label: 'State/county/city/school employee plan', hint: 'A government-employer plan (not federal)' },
  { value: 'stldi', label: 'Short-term health plan', hint: 'Temporary coverage — the card may say "not qualifying health coverage"' },
  { value: 'excepted_coverage', label: 'Health-sharing or fixed-indemnity plan', hint: 'A cost-sharing ministry or supplemental plan — not full insurance' },
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
