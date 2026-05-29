/**
 * Settings (Phase 2J) — real profile + improvement-consent toggle.
 *
 * Profile is read-only in V1-Lite (comes from OAuth in Phase 2K). The consent
 * toggle PATCHes /v1/user/me and takes effect immediately (no sign-out).
 * Notifications + account deletion are stubs until Phase 4; legal links point
 * at placeholder routes until Phase 7 publication.
 */

import { useCallback, useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, Switch, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { getUserProfile, updateConsent, type UserProfile } from '../../lib/api-client';

const CONSENT_FULL_TEXT = [
  'Help make Tyndale better. With your permission, we’ll use your bills, your feedback, and the outcomes of your cases — with all your personal information removed — to improve how Tyndale catches errors and helps people. This is optional, it never affects the service you receive, and you can turn it off anytime in Settings.',
  '',
  'What you are agreeing to, if you opt in: we may use your uploaded bills, your feedback (thumbs up/down and corrections), your confirmations (whether a billed service matched your care), and case outcomes — ONLY after de-identification, an automated + human-reviewed process that removes identifiers like your name, contact details, and member/account numbers.',
  '',
  'What you are NOT agreeing to: any use of information that still identifies you; any sale of your information; any advertising use; any sharing of your identifiable health or financial information with third parties for their own purposes.',
  '',
  'Withdrawing: you can turn this off anytime. After you withdraw, we stop using your information going forward. Information already fully de-identified may remain in our improvement datasets because it no longer identifies you.',
].join('\n');

export default function SettingsScreen() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [consentModal, setConsentModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);

  const load = useCallback(() => {
    getUserProfile().then(setProfile).catch(() => {/* non-fatal */});
  }, []);
  useEffect(() => load(), [load]);

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const onToggleConsent = async (value: boolean) => {
    if (!profile || busy) return;
    setBusy(true);
    setProfile({ ...profile, improvement_consent: value }); // optimistic
    try {
      const updated = await updateConsent(value);
      setProfile(updated);
      flash(value ? 'Thanks — you’re helping improve Tyndale.' : 'Turned off. We’ll stop using your data.');
    } catch {
      setProfile({ ...profile, improvement_consent: !value }); // revert
      flash('Couldn’t update — try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView className="flex-1 bg-navy-deep" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>
      <Text className="mb-6 text-3xl font-bold text-white">Settings</Text>

      {/* 1. Profile (read-only in V1-Lite) */}
      <Section title="Profile">
        <Row label="Name" value={profile?.first_name ?? '—'} />
        <Row label="Email" value={profile?.email ?? '—'} />
        <View className="mt-2 flex-row items-center justify-between">
          <Text className="text-sm text-white/60">Account type</Text>
          <View
            className={
              profile?.user_type === 'admin'
                ? 'rounded-full bg-sage/20 px-3 py-1'
                : 'rounded-full bg-white/10 px-3 py-1'
            }
          >
            <Text
              className={
                profile?.user_type === 'admin'
                  ? 'text-xs font-bold text-sage'
                  : 'text-xs font-semibold text-white/80'
              }
            >
              {profile?.user_type ?? 'user'}
            </Text>
          </View>
        </View>
      </Section>

      {/* 2. Improvement consent */}
      <Section title="Help us improve Tyndale">
        <Text className="text-sm leading-6 text-white/70">
          Help make Tyndale better. With your permission, we’ll use your bills and your feedback
          — with all your personal information removed — to improve how Tyndale catches errors.
          This is optional, never affects the service you receive, and you can turn it off anytime.
        </Text>
        <View className="mt-4 flex-row items-center justify-between">
          <Text className="text-base font-semibold text-white">Improve Tyndale with my data</Text>
          <Switch
            value={!!profile?.improvement_consent}
            onValueChange={onToggleConsent}
            disabled={busy || !profile}
            trackColor={{ false: 'rgba(255,255,255,0.15)', true: '#3DAA7E' }}
            thumbColor="#fff"
          />
        </View>
        <Pressable onPress={() => setConsentModal(true)} className="mt-3 self-start">
          <Text className="text-xs font-semibold text-sage">What does this share?</Text>
        </Pressable>
      </Section>

      {/* 3. Notifications (placeholder) */}
      <Section title="Notifications">
        <DisabledRow label="Email notifications" />
        <DisabledRow label="SMS notifications" />
        <Text className="mt-2 text-xs text-white/45">
          Notification preferences arrive when SendGrid + Twilio come online.
        </Text>
      </Section>

      {/* 4. Legal */}
      <Section title="Legal">
        <LinkRow label="Privacy Policy" onPress={() => router.push('/privacy')} />
        <LinkRow label="Terms of Service" onPress={() => router.push('/terms')} />
        <LinkRow label="Data Improvement Consent" onPress={() => setConsentModal(true)} />
      </Section>

      {/* 5. Account */}
      <Section title="Account">
        <LinkRow label="Sign Out" onPress={() => router.replace('/sign-in')} />
        <LinkRow label="Delete Account" tone="rose" onPress={() => setDeleteModal(true)} />
      </Section>

      <Text className="mt-8 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
        advice.
      </Text>

      {toast ? (
        <View className="mt-4 rounded-lg bg-sage/20 px-4 py-3">
          <Text className="text-center text-sm font-semibold text-sage">{toast}</Text>
        </View>
      ) : null}

      {/* Consent detail modal */}
      <Modal visible={consentModal} transparent animationType="slide" onRequestClose={() => setConsentModal(false)}>
        <View className="flex-1 justify-end bg-black/50">
          <View className="max-h-[80%] rounded-t-3xl bg-navy-soft p-6">
            <Text className="mb-3 text-xl font-bold text-white">Data Improvement Consent</Text>
            <ScrollView className="max-h-[60vh]">
              <Text className="text-sm leading-6 text-white/80">{CONSENT_FULL_TEXT}</Text>
            </ScrollView>
            <Pressable onPress={() => setConsentModal(false)} className="mt-4 rounded-xl bg-white/10 px-4 py-3">
              <Text className="text-center text-sm font-semibold text-white">Close</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      {/* Delete-account modal (stub) */}
      <Modal visible={deleteModal} transparent animationType="fade" onRequestClose={() => setDeleteModal(false)}>
        <View className="flex-1 items-center justify-center bg-black/60 p-6">
          <View className="w-full max-w-md rounded-2xl bg-navy-soft p-6">
            <Text className="text-xl font-bold text-white">Delete account?</Text>
            <Text className="mt-3 text-sm leading-6 text-white/70">
              We’ll delete your account and all your case files within 30 days. De-identified
              examples we’ve already promoted to improve Tyndale stay in our improvement dataset
              because they no longer identify you.
            </Text>
            <View className="mt-5 flex-row gap-3">
              <Pressable onPress={() => setDeleteModal(false)} className="flex-1 rounded-xl bg-white/10 px-4 py-3">
                <Text className="text-center text-sm font-semibold text-white">Cancel</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  // Stub — real deletion endpoint is Phase 4.
                  setDeleteModal(false);
                  flash('Deletion requested (stub — wired in Phase 4).');
                }}
                className="flex-1 rounded-xl bg-rose px-4 py-3"
              >
                <Text className="text-center text-sm font-bold text-white">Delete my account</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="mb-4 rounded-2xl border border-white/10 bg-navy-soft p-5">
      <Text className="mb-3 text-xs uppercase tracking-widest text-white/45">{title}</Text>
      {children}
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="mb-2 flex-row items-center justify-between">
      <Text className="text-sm text-white/60">{label}</Text>
      <Text className="text-sm text-white">{value}</Text>
    </View>
  );
}

function DisabledRow({ label }: { label: string }) {
  return (
    <View className="mb-2 flex-row items-center justify-between">
      <Text className="text-sm text-white/40">{label}</Text>
      <View className="rounded-full bg-white/5 px-2 py-0.5">
        <Text className="text-[10px] font-semibold text-white/40">Coming soon</Text>
      </View>
    </View>
  );
}

function LinkRow({
  label,
  onPress,
  tone,
}: {
  label: string;
  onPress: () => void;
  tone?: 'rose';
}) {
  return (
    <Pressable onPress={onPress} className="mb-1 flex-row items-center justify-between py-1.5">
      <Text className={tone === 'rose' ? 'text-sm text-rose' : 'text-sm text-white/90'}>{label}</Text>
      <Text className="text-sm text-white/30">›</Text>
    </Pressable>
  );
}
