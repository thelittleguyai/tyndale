/**
 * Statutory access / deletion / correction request (§A2 state 5 · deep review finding 4).
 *
 * The server route and its encrypted audit event have existed since the CS5 session; nothing
 * in the app called them. A statutory right with no way in is not an intake, so this is the
 * way in — one settings row to this screen.
 *
 * Two rules the UI has to hold up, both inherited from the route:
 *
 * 1. **It discloses nothing.** The confirmation is identical whether or not the named person
 *    appears anywhere in Tyndale. There is no "found / not found" branch to render, and the
 *    screen must never grow one — that branch IS the disclosure.
 * 2. **It promises only what happens.** The request is recorded and a person follows up at the
 *    contact given. We can't look anything up from here and the copy says so.
 *
 * Copy comes from the registry (`GET /v1/copy/access_request`) with engineering fallbacks, so
 * the wording of a legal-rights surface can be changed without shipping an app build.
 */
import { useEffect, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';

import {
  getSurfaceCopy,
  submitAccessRequest,
  type AccessRequestBody,
  type SurfaceCopy,
} from '../../lib/api-client';
import { Button } from '../../components/ui';
import { Screen } from '../../components/ui/Screen';
import { useThemeColors } from '../../theme/useThemeColors';

const REQUEST_TYPES: { key: AccessRequestBody['request_type']; label: string }[] = [
  { key: 'access', label: 'Show me what you hold' },
  { key: 'deletion', label: 'Delete it' },
  { key: 'correction', label: 'Correct something' },
];

/** Engineering fallbacks — the screen must render even if the copy call fails, because the
 *  route to a statutory right can't depend on a network round-trip succeeding. */
const FALLBACK = {
  type_label: 'What are you asking for?',
  name_label: 'Who is the request about?',
  contact_label: 'How should we reach you?',
  details_label: 'Anything else we should know? (optional)',
  submit: 'Send this request',
};

export default function AccessRequestScreen() {
  const router = useRouter();
  const [copy, setCopy] = useState<SurfaceCopy>({});
  const [requestType, setRequestType] = useState<AccessRequestBody['request_type']>('access');
  const [patientName, setPatientName] = useState('');
  const [contact, setContact] = useState('');
  const [details, setDetails] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSurfaceCopy('access_request').then(setCopy).catch(() => setCopy({}));
  }, []);

  const canSubmit = patientName.trim().length > 0 && contact.trim().length >= 3 && !submitting;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitAccessRequest({
        request_type: requestType,
        patient_name: patientName.trim(),
        contact: contact.trim(),
        details: details.trim() || undefined,
      });
      // The receipt is the server's authored line. We do NOT add to it, and we do not vary it
      // by request type — every variation is a signal about what we hold.
      setReceipt(res.message);
    } catch {
      setError("That didn't send — check your connection and try again.");
      setSubmitting(false);
    }
  };

  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 24, paddingTop: 32 }}>
      <Pressable onPress={() => router.back()} className="mb-6 self-start" testID="access-back">
        <Text className="text-sm text-secondary">← Back</Text>
      </Pressable>

      {receipt ? (
        <View testID="access-receipt">
          <Text className="text-title text-primary">Request received</Text>
          <Text className="mt-3 text-body leading-6 text-secondary">{receipt}</Text>
          <View className="mt-8">
            <Button variant="secondary" label="Done" onPress={() => router.back()} />
          </View>
        </View>
      ) : (
        <>
          <Text className="text-title text-primary">
            {copy.settings_label || 'Privacy requests'}
          </Text>
          {copy.intro ? (
            <Text className="mt-3 text-body leading-6 text-secondary">{copy.intro}</Text>
          ) : null}

          <Text className="mb-2 mt-7 text-caption text-faint">
            {copy.type_label || FALLBACK.type_label}
          </Text>
          <View className="gap-2">
            {REQUEST_TYPES.map((t) => (
              <Pressable
                key={t.key}
                onPress={() => setRequestType(t.key)}
                accessibilityRole="radio"
                accessibilityState={{ selected: requestType === t.key }}
                testID={`access-type-${t.key}`}
                className={`min-h-[44px] justify-center rounded-control border px-4 py-3 ${
                  requestType === t.key ? 'border-accent bg-inset' : 'border-hairline bg-surface'
                }`}
              >
                <Text className="text-body text-primary">{t.label}</Text>
              </Pressable>
            ))}
          </View>

          <Field
            label={copy.name_label || FALLBACK.name_label}
            value={patientName}
            onChangeText={setPatientName}
            testID="access-name"
          />
          <Field
            label={copy.contact_label || FALLBACK.contact_label}
            value={contact}
            onChangeText={setContact}
            autoCapitalize="none"
            testID="access-contact"
          />
          <Field
            label={copy.details_label || FALLBACK.details_label}
            value={details}
            onChangeText={setDetails}
            multiline
            testID="access-details"
          />

          <View className="mt-7">
            <Button
              variant="primary"
              disabled={!canSubmit}
              label={submitting ? 'Sending…' : copy.submit || FALLBACK.submit}
              onPress={submit}
              testID="access-submit"
            />
          </View>
          {error ? <Text className="mt-3 text-body text-danger">{error}</Text> : null}
        </>
      )}
      <View className="h-16" />
    </Screen>
  );
}

function Field({
  label,
  multiline,
  ...rest
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  multiline?: boolean;
  autoCapitalize?: 'none' | 'sentences';
  testID?: string;
}) {
  const tc = useThemeColors();
  return (
    <View className="mt-5">
      <Text className="mb-2 text-caption text-faint">{label}</Text>
      <TextInput
        {...rest}
        multiline={multiline}
        placeholderTextColor={tc.text.faint}
        className={`rounded-control border border-hairline bg-surface px-4 py-3 text-body text-primary ${
          multiline ? 'min-h-[88px]' : 'min-h-[44px]'
        }`}
      />
    </View>
  );
}
