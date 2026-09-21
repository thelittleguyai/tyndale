/**
 * Settings → Coverage type (2026-08-19, item 3). The 14-regime ladder with the detected candidate
 * preselected; confirming marks the regime verified (user_declared).
 *
 * This WAS a step of the CO-1A intake wizard (`/intake/coverage-regime-confirm?from=settings`).
 * Doc 40 replaced that wizard with the planner-driven `/intake`, whose own coverage ask is the
 * plain five-option screen — so this editor now lives with the surface that still uses it, and
 * carries no wizard chrome (it had a "Step 3 of 11" bar in Settings).
 */
import { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { router } from 'expo-router';

import type { CoverageRegime, RegimeDetection } from '@tyndale/shared';

import { getIntakeState, intakeConfirmRegime } from '../../lib/api-client';
import { Button } from '../../components/ui';
import { PressableScale } from '../../components/ui/PressableScale';
import { Screen } from '../../components/ui/Screen';
import { useThemeColors } from '../../theme/useThemeColors';

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

export default function CoverageTypeScreen() {
  const tc = useThemeColors();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [detection, setDetection] = useState<RegimeDetection | null>(null);
  const [selected, setSelected] = useState<CoverageRegime | ''>('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    // `latest`: the user's most recent case (created if they have none) — coverage type is
    // stored per case, and Settings edits the one the next audit will read.
    getIntakeState(undefined, { latest: true })
      .then((s) => {
        if (!alive) return;
        setCaseId(s.case_file_id);
        setDetection(s.captured_data.regime_detection ?? null);
        const current = s.captured_data.coverage_regime ?? s.captured_data.regime_detection?.candidate;
        if (current) setSelected(current);
      })
      .catch(() => alive && setError("We couldn't load your coverage type — check your connection and try again."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const onSave = async () => {
    if (!caseId || !selected) return;
    setBusy(true);
    setError(null);
    try {
      await intakeConfirmRegime(selected, caseId);
      router.back();
    } catch {
      setError("We couldn't save that — check your connection and try again.");
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-page">
        <ActivityIndicator color={tc.accent} />
      </View>
    );
  }

  const detectedLabel =
    detection?.candidate && REGIME_OPTIONS.find((o) => o.value === detection.candidate)?.label;

  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 24, paddingBottom: 48 }}>
      <PressableScale onPress={() => router.back()} className="mb-5 min-h-[44px] justify-center self-start">
        <Text className="text-body text-secondary">← Settings</Text>
      </PressableScale>
      <Text className="text-2xl font-bold text-primary">How are you covered?</Text>
      <Text className="mb-5 mt-2 text-body leading-6 text-secondary">
        {detectedLabel
          ? `From your card, this looks like ${detectedLabel}. Tap to confirm or change it.`
          : "Let's confirm your coverage type so I apply the right billing rules."}
      </Text>
      <View className="gap-2" accessibilityRole="radiogroup">
        {REGIME_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <PressableScale
              accessibilityRole="radio"
              accessibilityState={{ checked: active }}
              key={opt.value}
              onPress={() => setSelected(opt.value)}
              className={`min-h-[44px] rounded-2xl border p-4 ${
                active ? 'border-accent bg-accent-tint' : 'border-hairline bg-surface'
              }`}
            >
              <Text className={`text-base font-semibold ${active ? 'text-accent' : 'text-primary'}`}>
                {opt.label}
              </Text>
              <Text className="mt-0.5 text-[13px] leading-5 text-secondary">{opt.hint}</Text>
            </PressableScale>
          );
        })}
      </View>
      {error ? <Text className="mt-3 text-body text-danger">{error}</Text> : null}
      <Button
        label={busy ? 'Saving…' : selected ? 'Confirm' : 'Choose one to continue'}
        onPress={onSave}
        disabled={busy || !selected}
        fullWidth
        className="mt-6"
      />
    </Screen>
  );
}
