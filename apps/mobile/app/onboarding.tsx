/**
 * Profile onboarding (CO-17). The post-auth router (app/(app)/_layout.tsx) sends an
 * incomplete user here BEFORE the dashboard. Required: first + last name, DOB (18+),
 * and terms. The insurance card is optional (add it now or later in Settings). Lives
 * OUTSIDE the (app) group so the gate's redirect can't loop.
 */

import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { Redirect, router } from 'expo-router';

import { getProfileState, patchProfile } from '../lib/api-client';
import { CardUpload, formatPhone, validateDob } from '../lib/profile-ui';
import { useBreakpoint } from '../components/ui/use-breakpoint';
import { useCurrentUser } from '../lib/auth';

const TERMS_SUMMARY =
  'Tyndale helps you understand and question your medical bills. It provides billing and ' +
  'coverage advocacy — not medical, legal, or financial advice. Your documents are encrypted ' +
  'and never sold. By continuing you agree to the Terms of Service and Privacy Policy.';

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  error,
}: {
  label: string;
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  error?: string | null;
}) {
  return (
    <View className="mb-3">
      <Text className="mb-1 text-sm text-secondary">{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="rgba(255,255,255,0.3)"
        className="min-h-[44px] rounded-lg border border-hairline bg-inset px-3 py-2.5 text-base text-primary"
      />
      {error ? <Text className="mt-1 text-xs text-danger">{error}</Text> : null}
    </View>
  );
}

export default function Onboarding() {
  const { isPhone } = useBreakpoint();
  const { user, loading: authLoading } = useCurrentUser();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [dob, setDob] = useState('');
  const [phone, setPhone] = useState('');
  const [terms, setTerms] = useState(false);
  const [reviewedTerms, setReviewedTerms] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [uploading, setUploading] = useState({ front: false, back: false });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already complete (e.g. a back-nav) → go straight to the dashboard.
  useEffect(() => {
    getProfileState()
      .then((s) => {
        if (s.profile_completed) router.replace('/');
      })
      .catch(() => {});
  }, []);

  const dobCheck = useMemo(() => validateDob(dob), [dob]);
  const anyUploading = uploading.front || uploading.back;
  const canContinue =
    !!firstName.trim() &&
    !!lastName.trim() &&
    !!dobCheck.iso &&
    terms &&
    !anyUploading &&
    !submitting;

  const submit = async () => {
    if (!canContinue) return;
    setSubmitting(true);
    setError(null);
    try {
      await patchProfile({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        date_of_birth: dobCheck.iso,
        phone: phone.trim() || null,
        accept_terms: true,
      });
      router.replace('/');
    } catch {
      setError("We couldn't save your profile — check your connection and try again.");
      setSubmitting(false);
    }
  };

  // Auth guard (Phase 3.4): /onboarding lives outside the (app) group, so guard it here —
  // an unauthenticated visitor is bounced to sign-in, not shown the form (whose profile
  // fetch would 401 into a misleading "check your connection").
  if (authLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-page">
        <ActivityIndicator color="var(--c-accent)" />
      </View>
    );
  }
  if (!user) return <Redirect href="/sign-in" />;

  return (
    <ScrollView
      className="flex-1 bg-page"
      contentContainerStyle={{ padding: 20, paddingTop: 28, paddingBottom: 48 }}
    >
      <View className="w-full max-w-2xl self-center">
        <View className="mb-5 rounded-2xl bg-surface-raised p-5">
          <Text className="text-2xl font-bold leading-tight text-primary">Welcome to Tyndale</Text>
          <Text className="mt-2 text-[15px] leading-6 text-secondary">
            A few details so we can set up your account — this takes a minute.
          </Text>
        </View>

        <View className={isPhone ? '' : 'flex-row gap-3'}>
          <View className="flex-1">
            <Field label="First name" value={firstName} onChangeText={setFirstName} placeholder="Jane" />
          </View>
          <View className="flex-1">
            <Field label="Last name" value={lastName} onChangeText={setLastName} placeholder="Doe" />
          </View>
        </View>

        <Field
          label="Date of birth"
          value={dob}
          onChangeText={setDob}
          placeholder="MM/DD/YYYY"
          error={dobCheck.error}
        />
        <Field
          label="Phone (optional)"
          value={phone}
          onChangeText={(t) => setPhone(formatPhone(t))}
          placeholder="(555) 123-4567"
        />

        <Text className="mb-2 mt-4 text-sm font-semibold text-primary">Insurance card (optional)</Text>
        <Text className="mb-3 text-xs leading-5 text-faint">
          Add a photo and Tyndale reads your plan details automatically. You can skip this and add
          it later in Settings.
        </Text>
        <View className={isPhone ? 'gap-3' : 'flex-row gap-3'}>
          <View className="flex-1">
            <CardUpload side="front" onUploadingChange={(u) => setUploading((s) => ({ ...s, front: u }))} />
          </View>
          <View className="flex-1">
            <CardUpload side="back" onUploadingChange={(u) => setUploading((s) => ({ ...s, back: u }))} />
          </View>
        </View>

        {/* Terms — the checkbox unlocks only after the user opens "Review Terms". */}
        <View className="mt-5 rounded-2xl border border-hairline bg-surface p-4">
          <Pressable
            onPress={() => {
              setShowTerms((o) => !o);
              setReviewedTerms(true);
            }}
            className="min-h-[44px] flex-row items-center justify-between"
          >
            <Text className="text-body font-semibold text-accent">Review Terms of Service</Text>
            <Text className="text-sm text-faint">{showTerms ? '▲' : '▼'}</Text>
          </Pressable>
          {showTerms ? (
            <Text className="mt-2 text-xs leading-5 text-secondary">{TERMS_SUMMARY}</Text>
          ) : null}
          <Pressable
            onPress={() => reviewedTerms && setTerms((t) => !t)}
            disabled={!reviewedTerms}
            className="mt-3 min-h-[44px] flex-row items-center gap-3"
          >
            <View
              className={`h-6 w-6 items-center justify-center rounded-md border ${
                terms ? 'border-accent bg-accent' : 'border-hairline'
              } ${reviewedTerms ? '' : 'opacity-40'}`}
            >
              {terms ? <Text className="text-xs font-bold text-on-accent">✓</Text> : null}
            </View>
            <Text className={`flex-1 text-body ${reviewedTerms ? 'text-primary' : 'text-faint'}`}>
              I agree to the Terms of Service and Privacy Policy.
              {reviewedTerms ? '' : ' (Review first)'}
            </Text>
          </Pressable>
        </View>

        {error ? <Text className="mt-3 text-body text-danger">{error}</Text> : null}

        <Pressable
          disabled={!canContinue}
          onPress={submit}
          className={
            canContinue
              ? 'mt-6 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-4'
              : 'mt-6 min-h-[44px] items-center justify-center rounded-xl bg-inset px-4 py-4'
          }
        >
          <Text
            className={
              canContinue ? 'text-base font-bold text-on-accent' : 'text-base font-semibold text-faint'
            }
          >
            {submitting ? 'Saving…' : 'Continue to Tyndale'}
          </Text>
        </Pressable>

        <Text className="mt-10 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
          advice.
        </Text>
      </View>
    </ScrollView>
  );
}
