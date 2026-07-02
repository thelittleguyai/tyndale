/**
 * Shared chrome + primitives for the guided intake wizard (Phase CO-1A).
 *
 * Tone: warm, hand-holding, never interrogating. "Skip for now" is rendered as an
 * equal-weight secondary button (graceful degradation per the doctrines — skipping
 * is a first-class choice, not a buried link). Same dark navy / teal / sage tokens
 * as the rest of the app.
 */

import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { router } from 'expo-router';

import { INTAKE_STEPS, type IntakeStateResponse, type IntakeStep } from '@tyndale/shared';
import { getIntakeState, uploadDocuments, type UploadedDoc } from './api-client';
import { setIntakeDeferred } from './intake-deferred';

// Cached across step navigations so each screen shares one case file.
let _caseId: string | null = null;

/** One friendly save-failure message, shared by every step (no raw errors in the UI). */
export const SAVE_ERROR_MESSAGE =
  "We couldn't save that — check your connection and try again.";

export function nextStep(step: IntakeStep): IntakeStep {
  const i = INTAKE_STEPS.indexOf(step);
  return INTAKE_STEPS[Math.min(i + 1, INTAKE_STEPS.length - 1)];
}

export function goToStep(step: IntakeStep): void {
  router.push(`/intake/${step}` as never);
}

/** Loads (and caches) the intake state so a step knows its case_file_id + data. */
export function useWizard() {
  const [state, setState] = useState<IntakeStateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getIntakeState(_caseId ?? undefined)
      .then((s) => {
        if (!alive) return;
        _caseId = s.case_file_id;
        setState(s);
      })
      .catch(() => alive && setError("We couldn't load your progress — check your connection and try again."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return { state, caseId: state?.case_file_id ?? _caseId, loading, error };
}

const STEP_LABELS: Record<IntakeStep, string> = {
  welcome: 'Welcome',
  'insurance-card': 'Insurance card',
  'coverage-details': 'Coverage details',
  benefits: 'Plan benefits',
  deductible: 'Deductible',
  'oop-max': 'Out-of-pocket max',
  bills: 'Medical bills',
  eobs: 'EOBs',
  'visit-context': 'Your visit',
  complete: 'Done',
};

export function ProgressBar({ step }: { step: IntakeStep }) {
  const idx = INTAKE_STEPS.indexOf(step);
  return (
    <View>
      <Text className="mb-1.5 text-xs uppercase tracking-widest text-white/45">
        Step {idx + 1} of {INTAKE_STEPS.length} · {STEP_LABELS[step]}
      </Text>
      <View className="flex-row gap-1">
        {INTAKE_STEPS.map((s, i) => (
          <View
            key={s}
            className={`h-1.5 flex-1 rounded-full ${
              i < idx ? 'bg-sage' : i === idx ? 'bg-teal-deep' : 'bg-white/10'
            }`}
          />
        ))}
      </View>
    </View>
  );
}

export function WhyExpander({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <View className="mt-4">
      <Pressable onPress={() => setOpen((o) => !o)} className="self-start">
        <Text className="text-sm font-semibold text-sage">
          {open ? '− Why we need this' : '+ Why we need this'}
        </Text>
      </Pressable>
      {open ? (
        <Text className="mt-2 text-sm leading-6 text-white/70">{text}</Text>
      ) : null}
    </View>
  );
}

export function ExampleImage({ label }: { label: string }) {
  // Placeholder per the prompt — real sample images swap in post-launch.
  return (
    <View className="mt-4 items-center rounded-xl border border-dashed border-white/15 bg-navy-soft p-5">
      <Text className="text-xs uppercase tracking-wide text-white/40">Example</Text>
      <Text className="mt-1 text-center text-sm text-white/55">{label}</Text>
      <Text className="mt-1 text-[11px] text-white/30">(sample image coming soon)</Text>
    </View>
  );
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
}: {
  label: string;
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  keyboardType?: 'default' | 'numeric';
}) {
  return (
    <View className="mb-3">
      <Text className="mb-1 text-sm text-white/70">{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="rgba(255,255,255,0.3)"
        keyboardType={keyboardType ?? 'default'}
        className="rounded-lg border border-white/15 bg-black/20 px-3 py-2.5 text-base text-white"
      />
    </View>
  );
}

/** Web multi-file picker that uploads into the wizard's case file. */
export function UploadField({
  caseId,
  label,
  onUploaded,
}: {
  caseId: string;
  label: string;
  onUploaded: (docs: UploadedDoc[]) => void;
}) {
  const inputRef = useRef<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (Platform.OS !== 'web') {
    return (
      <View className="rounded-2xl border border-white/10 bg-navy-soft p-5">
        <Text className="text-sm text-white/80">
          Open Tyndale on the web to add documents for now — the native picker + camera
          capture arrive with the iOS/Android app.
        </Text>
      </View>
    );
  }

  const onPicked = async (e: any) => {
    const picked: FileList | undefined = e?.target?.files;
    if (!picked || picked.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await uploadDocuments(Array.from(picked), caseId);
      onUploaded(res.uploads);
    } catch {
      setError("We couldn't upload that — check your connection and try again.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <View>
      {/* react-native-web renders this as a real <input>. */}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,image/*"
        multiple
        onChange={onPicked}
        style={{ display: 'none' }}
      />
      <Pressable
        onPress={() => inputRef.current?.click?.()}
        className="items-center rounded-2xl border-2 border-dashed border-white/20 bg-navy-soft p-7"
      >
        {busy ? (
          <ActivityIndicator color="#3DAA7E" />
        ) : (
          <Text className="text-base font-semibold text-white">{label}</Text>
        )}
        <Text className="mt-1 text-xs text-white/50">PDF or image — pick one or several</Text>
      </Pressable>
      {error ? <Text className="mt-2 text-sm text-rose">{error}</Text> : null}
    </View>
  );
}

export function WizardShell({
  step,
  title,
  subtitle,
  why,
  example,
  children,
  onContinue,
  continueLabel = 'Continue',
  continueDisabled = false,
  busy = false,
  error,
  skippable = false,
  onSkip,
}: {
  step: IntakeStep;
  title: string;
  subtitle?: string;
  why?: string;
  example?: string;
  children?: React.ReactNode;
  onContinue?: () => void;
  continueLabel?: string;
  continueDisabled?: boolean;
  busy?: boolean;
  error?: string | null;
  skippable?: boolean;
  onSkip?: () => void;
}) {
  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ padding: 20, paddingTop: 22, paddingBottom: 48 }}
    >
      <View className="w-full max-w-2xl self-center">
      <View className="mb-5">
        <View className="mb-3 flex-row items-start justify-between">
          <View className="flex-1 pr-3">
            <ProgressBar step={step} />
          </View>
          <Pressable
            onPress={() => {
              // Mark intake as deferred for this session so the (app) layout
              // gate lets a mid-intake user reach the dashboard.
              setIntakeDeferred();
              router.push('/' as never);
            }}
            className="-mr-2 min-h-[44px] justify-center px-3 py-2"
          >
            <Text className="text-xs font-semibold text-white/60">Save &amp; exit</Text>
          </Pressable>
        </View>
      </View>

      <View className="mb-5 rounded-2xl bg-teal-deep p-5">
        <Text className="text-2xl font-bold leading-tight text-white">{title}</Text>
        {subtitle ? (
          <Text className="mt-2 text-[15px] leading-6 text-white/80">{subtitle}</Text>
        ) : null}
      </View>

      {children}
      {example ? <ExampleImage label={example} /> : null}
      {why ? <WhyExpander text={why} /> : null}
      {error ? <Text className="mt-3 text-sm text-rose">{error}</Text> : null}

      {onContinue ? (
        <Pressable
          disabled={continueDisabled || busy}
          onPress={onContinue}
          className={
            continueDisabled || busy
              ? 'mt-6 items-center rounded-xl bg-white/10 px-4 py-4'
              : 'mt-6 items-center rounded-xl bg-sage px-4 py-4'
          }
        >
          <Text
            className={
              continueDisabled || busy
                ? 'text-base font-semibold text-white/50'
                : 'text-base font-bold text-ink'
            }
          >
            {busy ? 'Saving…' : continueLabel}
          </Text>
        </Pressable>
      ) : null}

      {skippable && onSkip ? (
        <Pressable
          disabled={busy}
          onPress={onSkip}
          className="mt-3 items-center rounded-xl border border-white/20 px-4 py-4"
        >
          <Text className="text-base font-semibold text-white/80">Skip for now</Text>
        </Pressable>
      ) : null}

      <Text className="mt-10 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
      </View>
    </ScrollView>
  );
}

export function WizardLoading() {
  return (
    <View className="flex-1 items-center justify-center bg-navy-deep">
      <ActivityIndicator color="#fff" />
    </View>
  );
}
