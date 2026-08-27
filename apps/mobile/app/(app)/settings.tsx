/**
 * Settings (Phase 2J) — real profile + improvement-consent toggle.
 *
 * Profile is read-only in V1-Lite (comes from OAuth in Phase 2K). The consent
 * toggle PATCHes /v1/user/me and takes effect immediately (no sign-out).
 * Notifications + account deletion are stubs until Phase 4; legal links point
 * at placeholder routes until Phase 7 publication.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Linking, Modal, Platform, Pressable, ScrollView, Switch, Text, TextInput, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';

import {
  deletePlanDocument,
  deleteSecondaryInsurance,
  getBillingStatus,
  getInsuranceInfo,
  getIntakeState,
  getPlanDocuments,
  getProfileState,
  getSecondaryInsurance,
  getSurfaceCopy,
  getUserProfile,
  fetchCardImageObjectUrl,
  fetchPlanDocumentObjectUrl,
  patchProfile,
  putSecondaryInsurance,
  requestAccountDeletion,
  startBillingCheckout,
  updateConsent,
  uploadPlanDocument,
  type BillingStatus,
  type CardType,
  type InsuranceInfo,
  type PlanDocumentsPayload,
  type ProfileState,
  type SecondaryInsurance,
  type SurfaceCopy,
  type UserProfile,
} from '../../lib/api-client';
import { useSignOut } from '../../lib/auth';
import { clearIntakeDeferred } from '../../lib/intake-deferred';
import { PressableScale } from '../../components/ui/PressableScale';
import { Screen } from '../../components/ui/Screen';
import { Card, Disclosure, ThemeToggle } from '../../components/ui';
import { US_STATES, type UsState } from '@tyndale/shared';
import { CardUpload, formatPhone, isoToMdy, validateDob } from '../../lib/profile-ui';
import { useThemeColors } from '../../theme/useThemeColors';

const CONSENT_FULL_TEXT = [
  'Help make Tyndale better. With your permission, we’ll use your bills, your feedback, and the outcomes of your cases — with all your personal information removed — to improve how Tyndale catches errors and helps people. This is optional, it never affects the service you receive, and you can turn it off anytime in Settings.',
  '',
  'What you are agreeing to, if you opt in: we may use your uploaded bills, your feedback (thumbs up/down and corrections), your confirmations (whether a billed service matched your care), and case outcomes — ONLY after de-identification, an automated + human-reviewed process that removes identifiers like your name, contact details, and member/account numbers.',
  '',
  'What you are NOT agreeing to: any use of information that still identifies you; any sale of your information; any advertising use; any sharing of your identifiable health or financial information with third parties for their own purposes.',
  '',
  'Withdrawing: you can turn this off anytime. After you withdraw, we stop using your information going forward. Information already fully de-identified may remain in our improvement datasets because it no longer identifies you.',
].join('\n');

// Plain-language labels for the 14 coverage regimes (Brock 2026-07-06, DL-90).
const REGIME_LABELS: Record<string, string> = {
  state_regulated_commercial: 'Commercial / employer',
  erisa_self_funded: 'Self-funded employer (ERISA)',
  medicare_traditional: 'Original Medicare',
  medicare_advantage: 'Medicare Advantage',
  medicaid_ffs: 'Medicaid',
  medicaid_mco: 'Medicaid managed care',
  dual_eligible: 'Medicare + Medicaid',
  tricare: 'TRICARE',
  va_champva: 'VA / CHAMPVA',
  fehb_pshb: 'Federal / postal (FEHB/PSHB)',
  nonfederal_governmental: 'State / local government',
  stldi: 'Short-term plan',
  excepted_coverage: 'Health-sharing / indemnity',
  self_pay: 'No insurance (self-pay)',
};

export default function SettingsScreen() {
  const c = useThemeColors();
  const router = useRouter();
  const signOut = useSignOut();
  const [signingOut, setSigningOut] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [pstate, setPstate] = useState<ProfileState | null>(null);
  const [settingsCopy, setSettingsCopy] = useState<SurfaceCopy | null>(null);
  const [insurance, setInsurance] = useState<InsuranceInfo | null>(null);
  const [coverageType, setCoverageType] = useState<string | null>(null);
  // Secondary plan (2026-08-19, item 4) — display + edit only; COB math is B6 (Brock).
  const [secondary, setSecondary] = useState<SecondaryInsurance | null>(null);
  const [editingSecondary, setEditingSecondary] = useState(false);
  const [secInsurer, setSecInsurer] = useState('');
  const [secMemberId, setSecMemberId] = useState('');
  const [secPlanType, setSecPlanType] = useState<string | null>(null);
  const [savingSecondary, setSavingSecondary] = useState(false);
  const [confirmRemoveSecondary, setConfirmRemoveSecondary] = useState(false);
  // Plan documents (2026-08-19, item 5) — the plan-level SBC home.
  const [planDocs, setPlanDocs] = useState<PlanDocumentsPayload | null>(null);
  const [fn, setFn] = useState('');
  const [ln, setLn] = useState('');
  const [dob, setDob] = useState('');
  const [phone, setPhone] = useState('');
  const [usState, setUsState] = useState('');
  const [addr1, setAddr1] = useState('');
  const [addr2, setAddr2] = useState('');
  const [city, setCity] = useState('');
  const [zip, setZip] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [consentModal, setConsentModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    getUserProfile().then(setProfile).catch(() => {/* non-fatal */});
    getSurfaceCopy('settings').then(setSettingsCopy).catch(() => {/* fallbacks render */});
    getProfileState()
      .then((s) => {
        setPstate(s);
        setFn(s.first_name ?? '');
        setLn(s.last_name ?? '');
        setDob(isoToMdy(s.date_of_birth));
        setPhone(s.phone ?? '');
        setUsState(s.state ?? '');
        setAddr1(s.address_line1 ?? '');
        setAddr2(s.address_line2 ?? '');
        setCity(s.city ?? '');
        setZip(s.zip_code ?? '');
      })
      .catch(() => {/* non-fatal */});
    getInsuranceInfo().then(setInsurance).catch(() => {/* non-fatal */});
    getSecondaryInsurance().then(setSecondary).catch(() => {/* non-fatal */});
    getPlanDocuments().then(setPlanDocs).catch(() => {/* non-fatal */});
    // Detected/confirmed coverage regime (DL-82) — from the user's active case.
    getIntakeState()
      .then((s) => {
        const cd = s.captured_data;
        if (cd.coverage_regime) {
          setCoverageType(REGIME_LABELS[cd.coverage_regime] ?? cd.coverage_regime);
        } else if (cd.regime_detection?.candidate) {
          const label = REGIME_LABELS[cd.regime_detection.candidate] ?? cd.regime_detection.candidate;
          setCoverageType(`${label} (unconfirmed)`);
        } else {
          setCoverageType(null);
        }
      })
      .catch(() => {/* non-fatal */});
  }, []);
  // Focus-driven (2026-08-19): returning from the coverage ladder (or any
  // sub-screen) refreshes the rows, so a just-confirmed regime shows immediately.
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const flash = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const dobCheck = validateDob(dob);
  const saveProfile = async () => {
    if (savingProfile) return;
    setSavingProfile(true);
    try {
      const updated = await patchProfile({
        first_name: fn.trim() || null,
        last_name: ln.trim() || null,
        date_of_birth: dob.trim() ? dobCheck.iso : null,
        phone: phone.trim() || null,
        state: usState.trim() || null,
        address_line1: addr1.trim() || null,
        address_line2: addr2.trim() || null,
        city: city.trim() || null,
        zip_code: zip.trim() || null,
      });
      setPstate(updated);
      flash('Profile saved.');
    } catch {
      flash('Couldn’t save — check the fields and try again.');
    } finally {
      setSavingProfile(false);
    }
  };

  const startEditSecondary = () => {
    setSecInsurer(secondary?.insurer ?? '');
    setSecMemberId(secondary?.member_id ?? '');
    setSecPlanType(secondary?.plan_type ?? null);
    setEditingSecondary(true);
  };

  const saveSecondary = async () => {
    if (savingSecondary) return;
    setSavingSecondary(true);
    try {
      const updated = await putSecondaryInsurance({
        insurer: secInsurer.trim() || null,
        member_id: secMemberId.trim() || null,
        plan_type: secPlanType,
      });
      setSecondary(updated);
      setEditingSecondary(false);
      flash('Secondary plan saved.');
    } catch {
      flash('Couldn’t save the secondary plan — try again.');
    } finally {
      setSavingSecondary(false);
    }
  };

  const removeSecondary = async () => {
    // Two-tap confirm: the first tap arms, the second deletes (row + both card photos).
    if (!confirmRemoveSecondary) {
      setConfirmRemoveSecondary(true);
      setTimeout(() => setConfirmRemoveSecondary(false), 4000);
      return;
    }
    setConfirmRemoveSecondary(false);
    try {
      await deleteSecondaryInsurance();
      setEditingSecondary(false);
      flash('Secondary plan removed.');
      load();
    } catch {
      flash('Couldn’t remove it — try again.');
    }
  };

  const viewPlanDoc = async (id: string) => {
    const url = await fetchPlanDocumentObjectUrl(id);
    if (url && typeof window !== 'undefined') window.open(url, '_blank');
  };

  const removePlanDoc = async (id: string) => {
    try {
      await deletePlanDocument(id);
      flash('Document removed.');
      load();
    } catch {
      flash('Couldn’t remove it — try again.');
    }
  };

  const onSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await signOut(); // clears the server cookie + local token
    } catch {
      // Best effort — navigate to sign-in regardless so the user isn't stuck.
    }
    clearIntakeDeferred();
    router.replace('/sign-in');
  };

  const onDeleteAccount = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await requestAccountDeletion();
      setDeleteModal(false);
      await signOut(); // server invalidated the session + cleared the cookie; clear local too
      clearIntakeDeferred();
      router.replace('/sign-in');
    } catch {
      setDeleting(false);
      flash('Couldn’t delete your account — try again or contact support.');
    }
  };

  const toggleEmailNotifications = async (value: boolean) => {
    if (!pstate) return;
    setPstate({ ...pstate, email_notifications_enabled: value }); // optimistic
    try {
      setPstate(await patchProfile({ email_notifications_enabled: value }));
      flash(value ? 'Reminders on.' : 'Reminders off — case updates still arrive.');
    } catch {
      setPstate({ ...pstate, email_notifications_enabled: !value }); // revert
      flash('Couldn’t update — try again.');
    }
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
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <Pressable
        onPress={() => router.push('/')}
        className="mb-5 self-start active:opacity-70"
      >
        <Text className="text-sm text-secondary hover:text-primary">← Back to dashboard</Text>
      </Pressable>
      <Text className="mb-6 text-3xl font-bold text-primary">Settings</Text>

      {/* Appearance — theme toggle (redesign §3). This block is on the new "Clear day / Midnight
          ledger" tokens, so it flips light↔dark as you switch; the rest of the app takes on the
          new look as its screens are converted. */}
      <Card className="mb-4">
        <Text className="mb-3 text-caption text-secondary">Appearance</Text>
        <ThemeToggle />
        <Text className="mt-3 text-body text-secondary">
          Choose Light, Dark, or follow your device. More of the app takes on the new look as
          screens are updated.
        </Text>
      </Card>

      {/* 1. Profile (editable — CO-17) */}
      <Section title="Profile">
        <View className="flex-row gap-3">
          <View className="flex-1">
            <EditField label="First name" value={fn} onChangeText={setFn} placeholder="Jane" />
          </View>
          <View className="flex-1">
            <EditField label="Last name" value={ln} onChangeText={setLn} placeholder="Doe" />
          </View>
        </View>
        <EditField
          label="Date of birth"
          value={dob}
          onChangeText={setDob}
          placeholder="MM/DD/YYYY"
          error={dobCheck.error}
        />
        <EditField
          label="Phone"
          value={phone}
          onChangeText={(t) => setPhone(formatPhone(t))}
          placeholder="(555) 123-4567"
        />
        {/* State of residence (2026-08-19, item 2) — the jurisdiction field. A document-
            derived suggestion prefills as a CONFIRM chip, never a silent write. */}
        <EditField
          label="State"
          value={usState}
          onChangeText={(t) => setUsState(t.toUpperCase().slice(0, 2))}
          placeholder="WI"
          error={usState && !US_STATES.includes(usState as UsState) ? 'Two-letter US state code' : undefined}
        />
        {!usState && pstate?.suggested_state ? (
          <Pressable
            onPress={() => setUsState(pstate.suggested_state ?? '')}
            className="mb-2 self-start rounded-full bg-accent-tint px-3 py-1"
            testID="state-suggestion-chip"
          >
            <Text className="text-xs font-semibold text-accent">
              We spotted {pstate.suggested_state} on your documents — use it?
            </Text>
          </Pressable>
        ) : null}
        <Disclosure summary="Mailing address (optional)">
          <EditField label="Address line 1" value={addr1} onChangeText={setAddr1} placeholder="123 Main St" />
          <EditField label="Address line 2" value={addr2} onChangeText={setAddr2} placeholder="Apt 4" />
          <View className="flex-row gap-3">
            <View className="flex-1">
              <EditField label="City" value={city} onChangeText={setCity} placeholder="Beloit" />
            </View>
            <View className="w-28">
              <EditField label="ZIP" value={zip} onChangeText={setZip} placeholder="53511" />
            </View>
          </View>
        </Disclosure>
        <Row label="Email" value={pstate?.email ?? profile?.email ?? '—'} />
        <View className="mt-2 flex-row items-center justify-between">
          <Text className="text-sm text-secondary">Account type</Text>
          <View
            className={
              profile?.user_type === 'admin'
                ? 'rounded-full bg-accent-tint px-3 py-1'
                : 'rounded-full bg-inset px-3 py-1'
            }
          >
            <Text
              className={
                profile?.user_type === 'admin'
                  ? 'text-xs font-bold text-accent'
                  : 'text-xs font-semibold text-secondary'
              }
            >
              {profile?.user_type ?? 'user'}
            </Text>
          </View>
        </View>
        <PressableScale
          onPress={saveProfile}
          className="mt-4 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
        >
          <Text className="text-body font-bold text-on-accent">
            {savingProfile ? 'Saving…' : 'Save profile'}
          </Text>
        </PressableScale>
      </Section>

      {/* 1b. Insurance (CO-17) */}
      <Section title="Insurance">
        <Row label="Insurer" value={insurance?.insurer ?? '—'} />
        <Row label="Member ID" value={insurance?.member_id ?? '—'} />
        <Row label="Plan" value={insurance?.plan_name ?? '—'} />
        {/* Item 3 (2026-08-19): "Not set" is now SETTABLE — the same verification ladder
            intake uses, same confirm path (user_declared, verified). */}
        <Pressable
          onPress={() => router.push('/intake/coverage-regime-confirm?from=settings')}
          className="flex-row items-center justify-between py-1"
          testID="coverage-type-row"
        >
          <Text className="text-sm text-secondary">Coverage type</Text>
          <Text className={coverageType ? 'text-sm text-primary' : 'text-sm text-accent'}>
            {coverageType ?? 'Set it →'}
          </Text>
        </Pressable>
        <Text className="mb-2 mt-3 text-xs text-faint">Card photos</Text>
        <View className="flex-row gap-3">
          <View className="flex-1">
            <CardThumb side="front" present={!!insurance?.has_front} />
            <CardUpload side="front" initialDone={!!insurance?.has_front} onResult={() => load()} />
          </View>
          <View className="flex-1">
            <CardThumb side="back" present={!!insurance?.has_back} />
            <CardUpload side="back" initialDone={!!insurance?.has_back} onResult={() => load()} />
          </View>
        </View>

        {/* Secondary coverage (2026-08-19, item 4) — capture + display only. Coordination-of-
            benefits math is Brock's pending content (B6); nothing here computes with it. */}
        <Text className="mb-2 mt-4 text-xs text-faint">Secondary coverage</Text>
        {secondary?.exists && !editingSecondary ? (
          <>
            <Row label="Insurer" value={secondary.insurer ?? '—'} />
            <Row label="Member ID" value={secondary.member_id ?? '—'} />
            <Row
              label="Plan type"
              value={
                secondary.plan_type
                  ? (REGIME_LABELS[secondary.plan_type] ?? secondary.plan_type)
                  : '—'
              }
            />
            <Text className="mb-2 mt-3 text-xs text-faint">Card photos (secondary)</Text>
            <View className="flex-row gap-3">
              <View className="flex-1">
                <CardThumb side="secondary_front" present={!!secondary.has_front} />
                <CardUpload
                  side="front"
                  cardType="secondary_front"
                  initialDone={!!secondary.has_front}
                  onResult={() => load()}
                />
              </View>
              <View className="flex-1">
                <CardThumb side="secondary_back" present={!!secondary.has_back} />
                <CardUpload
                  side="back"
                  cardType="secondary_back"
                  initialDone={!!secondary.has_back}
                  onResult={() => load()}
                />
              </View>
            </View>
            <View className="mt-3 flex-row gap-5">
              <Pressable onPress={startEditSecondary} testID="secondary-edit" className="min-h-[32px] justify-center">
                <Text className="text-sm font-semibold text-accent">Edit</Text>
              </Pressable>
              <Pressable onPress={removeSecondary} testID="secondary-remove" className="min-h-[32px] justify-center">
                <Text className="text-sm font-semibold text-danger">
                  {confirmRemoveSecondary ? 'Tap again to remove' : 'Remove'}
                </Text>
              </Pressable>
            </View>
          </>
        ) : editingSecondary ? (
          <View>
            <EditField
              label="Insurer"
              value={secInsurer}
              onChangeText={setSecInsurer}
              placeholder="e.g. Aetna"
            />
            <EditField
              label="Member ID"
              value={secMemberId}
              onChangeText={setSecMemberId}
              placeholder="On the card"
            />
            <Text className="mb-1 text-sm text-secondary">Plan type</Text>
            <View className="mb-3 flex-row flex-wrap gap-2">
              {/* Same regime vocabulary as the primary — minus self_pay, which can't be a
                  SECOND plan. Tap the selected chip again to clear. */}
              {Object.entries(REGIME_LABELS)
                .filter(([value]) => value !== 'self_pay')
                .map(([value, label]) => (
                  <Pressable
                    key={value}
                    onPress={() => setSecPlanType(secPlanType === value ? null : value)}
                    className={
                      secPlanType === value
                        ? 'rounded-full bg-accent px-3 py-1.5'
                        : 'rounded-full bg-inset px-3 py-1.5'
                    }
                  >
                    <Text
                      className={
                        secPlanType === value
                          ? 'text-xs font-semibold text-on-accent'
                          : 'text-xs text-secondary'
                      }
                    >
                      {label}
                    </Text>
                  </Pressable>
                ))}
            </View>
            <View className="flex-row gap-3">
              <PressableScale
                onPress={saveSecondary}
                className="min-h-[44px] flex-1 items-center justify-center rounded-xl bg-accent px-4"
                testID="secondary-save"
              >
                <Text className="text-body font-bold text-on-accent">
                  {savingSecondary ? 'Saving…' : 'Save'}
                </Text>
              </PressableScale>
              <PressableScale
                onPress={() => setEditingSecondary(false)}
                className="min-h-[44px] flex-1 items-center justify-center rounded-xl bg-inset px-4"
              >
                <Text className="text-body font-semibold text-secondary">Cancel</Text>
              </PressableScale>
            </View>
          </View>
        ) : (
          <>
            {secondary?.captured_hint ? (
              <Text className="mb-2 text-sm text-secondary">{secondary.captured_hint}</Text>
            ) : null}
            <Pressable
              onPress={startEditSecondary}
              testID="secondary-add"
              className="min-h-[32px] justify-center self-start"
            >
              <Text className="text-sm font-semibold text-accent">+ Add a secondary plan</Text>
            </Pressable>
          </>
        )}
      </Section>

      {/* 1c. Plan documents (2026-08-19, item 5) — the plan-level SBC home. One upload
          satisfies the SBC line on every case's checklist and feeds its coverage terms
          to the audit. Copy keys come from the settings surface; fallbacks render until
          Brock authors them (absent-from-registry, never [PLACEHOLDER-eng]). */}
      <Section title={settingsCopy?.plan_documents_title ?? 'Plan documents'}>
        <Text className="text-body leading-6 text-secondary">
          {settingsCopy?.plan_documents_description ??
            'Your Summary of Benefits and Coverage (SBC) describes your plan, not one bill — add it once here and every case can use it.'}
        </Text>
        {planDocs?.sbc_on_file ? (
          <View className="mt-3 self-start rounded-full bg-accent-tint px-3 py-1" testID="sbc-on-file">
            <Text className="text-xs font-semibold text-accent">
              {settingsCopy?.plan_documents_sbc_on_file ??
                '✓ SBC on file — your cases won’t ask for it again'}
            </Text>
          </View>
        ) : (
          <Text className="mt-3 text-sm text-faint">
            {settingsCopy?.plan_documents_empty ?? 'No plan documents yet.'}
          </Text>
        )}
        {(planDocs?.documents ?? []).map((d) => (
          <View
            key={d.plan_document_id}
            className="mt-3 flex-row items-center justify-between gap-3"
          >
            <View className="flex-1">
              <Text className="text-body text-primary" numberOfLines={1}>
                {d.filename}
              </Text>
              <Text className="text-xs text-faint">
                {d.is_sbc
                  ? d.has_coverage_terms
                    ? 'SBC — plan terms read'
                    : 'SBC — on file (terms not readable)'
                  : `Looks like: ${d.document_type.replace(/_/g, ' ')}`}
              </Text>
            </View>
            <Pressable
              onPress={() => void viewPlanDoc(d.plan_document_id)}
              className="min-h-[32px] justify-center"
            >
              <Text className="text-sm font-semibold text-accent">View</Text>
            </Pressable>
            <Pressable
              onPress={() => void removePlanDoc(d.plan_document_id)}
              className="min-h-[32px] justify-center"
              testID={`plan-doc-remove-${d.plan_document_id}`}
            >
              <Text className="text-sm font-semibold text-danger">Remove</Text>
            </Pressable>
          </View>
        ))}
        <PlanDocUpload onDone={() => load()} />
      </Section>

      {/* 2. Improvement consent */}
      <Section title="Help us improve Tyndale">
        <Text className="text-body leading-6 text-secondary">
          Help make Tyndale better. With your permission, we’ll use your bills and your feedback
          — with all your personal information removed — to improve how Tyndale catches errors.
          This is optional, never affects the service you receive, and you can turn it off anytime.
        </Text>
        <View className="mt-4 flex-row items-center justify-between">
          <Text className="text-base font-semibold text-primary">Improve Tyndale with my data</Text>
          <Switch
            value={!!profile?.improvement_consent}
            onValueChange={onToggleConsent}
            disabled={busy || !profile}
            trackColor={{ false: c.border.strong, true: c.accent }}
            thumbColor={c.bg.surface}
          />
        </View>
        <Pressable
          onPress={() => setConsentModal(true)}
          className="mt-3 self-start active:opacity-70"
        >
          <Text className="text-xs font-semibold text-accent hover:text-accent">
            What does this share?
          </Text>
        </Pressable>
      </Section>

      {/* 3. Notifications — the email toggle is REAL (SendGrid live, 2026-08-19). It gates
          REMINDERS only (nudge chases + check-ins); case updates always arrive. SMS stays an
          honest "Coming soon" (Twilio undecided). Copy from the settings surface; unauthored
          keys are withheld server-side and these fallbacks render (the capture precedent). */}
      <Section title="Notifications">
        <View className="flex-row items-center justify-between py-1">
          <View className="flex-1 pr-3">
            <Text className="text-body text-primary">
              {settingsCopy?.notifications_email_label ?? 'Email notifications'}
            </Text>
            <Text className="mt-0.5 text-xs text-faint">
              {settingsCopy?.notifications_email_description ??
                'Case updates always arrive — this controls reminders and check-ins.'}
            </Text>
          </View>
          <Switch
            value={pstate?.email_notifications_enabled ?? true}
            onValueChange={toggleEmailNotifications}
            disabled={!pstate}
            testID="email-notifications-toggle"
          />
        </View>
        <DisabledRow label={settingsCopy?.notifications_sms_label ?? 'SMS notifications'} />
      </Section>

      {/* Billing (Item 4) — renders nothing while the dark scaffold is off (enabled:false). */}
      <BillingSection />

      {/* 4. Legal */}
      <Section title="Legal">
        <LinkRow label="Privacy Policy" onPress={() => router.push('/privacy')} />
        <LinkRow label="Terms of Service" onPress={() => router.push('/terms')} />
        <LinkRow label="Data Improvement Consent" onPress={() => setConsentModal(true)} />
        {/* The way in to the statutory-rights intake (deep review finding 4). The route and its
            encrypted event already existed; without this row nobody could reach them. */}
        <LinkRow
          label="Privacy requests — access or delete data"
          onPress={() => router.push('/access-request')}
        />
      </Section>

      {/* 5. Account */}
      <Section title="Account">
        {profile?.user_type === 'admin' ? (
          // Mirrors the header's Admin jump-off; on narrow widths the header collapses
          // Admin + Sign Out into here (2026-08-26 viewport sweep). DL-60: non-admins
          // never see this row.
          <LinkRow
            label="Admin console"
            onPress={() => Linking.openURL('https://admin.tyndaleapp.net').catch(() => {})}
          />
        ) : null}
        <LinkRow label={signingOut ? 'Signing out…' : 'Sign Out'} onPress={onSignOut} />
        <LinkRow label="Delete Account" tone="rose" onPress={() => setDeleteModal(true)} />
      </Section>

      <Text className="mt-8 text-center text-xs text-faint">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
        advice.
      </Text>

      {toast ? (
        <View className="mt-4 rounded-lg bg-accent-tint px-4 py-3">
          <Text className="text-center text-body font-semibold text-accent">{toast}</Text>
        </View>
      ) : null}

      {/* Consent detail modal */}
      <Modal visible={consentModal} transparent animationType="slide" onRequestClose={() => setConsentModal(false)}>
        <View className="flex-1 justify-end bg-black/50">
          <View className="max-h-[80%] rounded-t-3xl bg-surface p-6">
            <Text className="mb-3 text-xl font-bold text-primary">Data Improvement Consent</Text>
            <ScrollView className="max-h-[60vh]">
              <Text className="text-body leading-6 text-secondary">{CONSENT_FULL_TEXT}</Text>
            </ScrollView>
            <PressableScale
              onPress={() => setConsentModal(false)}
              className="mt-4 rounded-xl bg-inset px-4 py-3 hover:bg-inset"
            >
              <Text className="text-center text-body font-semibold text-primary">Close</Text>
            </PressableScale>
          </View>
        </View>
      </Modal>

      {/* Delete-account modal (stub) */}
      <Modal visible={deleteModal} transparent animationType="fade" onRequestClose={() => setDeleteModal(false)}>
        <View className="flex-1 items-center justify-center bg-black/60 p-6">
          <View className="w-full max-w-md rounded-2xl bg-surface p-6">
            <Text className="text-xl font-bold text-primary">Delete account?</Text>
            <Text className="mt-3 text-body leading-6 text-secondary">
              This removes your name, contact info, and insurance details from Tyndale and signs
              you out right away. De-identified examples we’ve already promoted to improve Tyndale
              stay in our improvement dataset because they no longer identify you.
            </Text>
            <View className="mt-5 flex-row gap-3">
              <PressableScale
                onPress={() => setDeleteModal(false)}
                disabled={deleting}
                className="flex-1 rounded-xl bg-inset px-4 py-3 hover:bg-inset"
              >
                <Text className="text-center text-body font-semibold text-primary">Cancel</Text>
              </PressableScale>
              <PressableScale
                onPress={onDeleteAccount}
                disabled={deleting}
                className="flex-1 rounded-xl bg-danger px-4 py-3 hover:opacity-90"
              >
                <Text className="text-center text-body font-bold text-primary">
                  {deleting ? 'Deleting…' : 'Delete my account'}
                </Text>
              </PressableScale>
            </View>
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="mb-4 rounded-2xl border border-hairline bg-surface p-5 shadow-card">
      <Text className="mb-3 text-xs text-faint">{title}</Text>
      {children}
    </View>
  );
}

// Item 4 — flag-hidden billing (DL-16). While the dark scaffold is off the API returns
// {enabled:false} and this renders NOTHING; when billing is enabled it shows the subscription
// state + plan CTAs (Stripe hosted Checkout, opened in the browser).
function BillingSection() {
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getBillingStatus()
      .then(setBilling)
      .catch(() => setBilling({ enabled: false }));
  }, []);

  if (!billing || !billing.enabled) return null; // hidden while the scaffold is dark

  const subscribe = async (plan: 'monthly' | 'yearly') => {
    if (busy) return;
    setBusy(true);
    try {
      const url = await startBillingCheckout(plan);
      await Linking.openURL(url);
    } catch {
      // best-effort; leave the section interactive
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title="Subscription">
      {billing.active ? (
        <Row label="Plan" value={billing.plan === 'yearly' ? 'Yearly ($100/yr)' : 'Monthly ($11.99/mo)'} />
      ) : (
        <>
          <Text className="mb-3 text-body leading-6 text-secondary">
            You have {billing.free_analyses_remaining ?? 0} free bill{' '}
            {(billing.free_analyses_remaining ?? 0) === 1 ? 'analysis' : 'analyses'} left. Subscribe
            for unlimited checks.
          </Text>
          <View className="flex-row gap-3">
            <PressableScale
              onPress={() => subscribe('monthly')}
              className="flex-1 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
            >
              <Text className="text-body font-bold text-on-accent">$11.99 / month</Text>
            </PressableScale>
            <PressableScale
              onPress={() => subscribe('yearly')}
              className="flex-1 min-h-[44px] items-center justify-center rounded-xl border border-accent px-4 py-3 hover:bg-inset"
            >
              <Text className="text-body font-bold text-accent">$100 / year</Text>
            </PressableScale>
          </View>
        </>
      )}
    </Section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="mb-2 flex-row items-center justify-between">
      <Text className="text-sm text-secondary">{label}</Text>
      <Text className="text-sm text-primary">{value}</Text>
    </View>
  );
}

function EditField({
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
  const tc = useThemeColors();
  return (
    <View className="mb-3">
      <Text className="mb-1 text-sm text-secondary">{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={tc.text.faint}
        className="min-h-[44px] rounded-lg border border-hairline bg-inset px-3 py-2.5 text-base text-primary"
      />
      {error ? <Text className="mt-1 text-xs text-danger">{error}</Text> : null}
    </View>
  );
}

/** Web file-pick → POST /v1/plan/documents. Native mirrors the card-upload note until
 *  the native document picker lands. Honest result copy: an upload that classifies OFF
 *  the SBC family is saved but told apart — it doesn't check the SBC box. */
function PlanDocUpload({ onDone }: { onDone: () => void }) {
  const inputRef = useRef<any>(null);
  const [state, setState] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle');
  const [msg, setMsg] = useState<string | null>(null);

  if (Platform.OS !== 'web') {
    return (
      <Text className="mt-3 text-sm text-faint">
        Open Tyndale on the web to add plan documents — the native picker arrives with the
        iOS / Android app.
      </Text>
    );
  }

  const onPicked = async (e: any) => {
    const file: File | undefined = e?.target?.files?.[0];
    if (!file) return;
    setState('uploading');
    setMsg(null);
    try {
      const r = await uploadPlanDocument(file);
      setState('done');
      setMsg(
        r.is_sbc
          ? r.has_coverage_terms
            ? 'Got it — your SBC is on file and its plan terms were read.'
            : 'Your SBC is on file. I couldn’t read the numbers from it, but cases won’t ask for it again.'
          : 'Saved — though this doesn’t look like a benefits summary (SBC), so it won’t check the SBC box.',
      );
    } catch (err) {
      setState('error');
      setMsg(
        String(err instanceof Error ? err.message : '').includes('422')
          ? 'That file won’t work — upload your SBC as a PDF or a clear photo.'
          : 'Couldn’t upload that — check your connection and try again.',
      );
    } finally {
      if (inputRef.current) inputRef.current.value = '';
      onDone();
    }
  };

  return (
    <View className="mt-4">
      {/* react-native-web renders this as a real DOM <input>. */}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,image/*"
        onChange={onPicked}
        style={{ display: 'none' }}
      />
      <PressableScale
        onPress={() => inputRef.current?.click?.()}
        className="min-h-[44px] items-center justify-center rounded-xl bg-inset px-4 py-3"
        testID="plan-doc-upload"
      >
        <Text className="text-body font-semibold text-primary">
          {state === 'uploading' ? 'Uploading…' : '+ Add a plan document'}
        </Text>
      </PressableScale>
      {msg ? (
        <Text
          className={
            state === 'error' ? 'mt-2 text-sm text-danger' : 'mt-2 text-sm text-secondary'
          }
        >
          {msg}
        </Text>
      ) : null}
    </View>
  );
}

function CardThumb({ side, present }: { side: CardType; present: boolean }) {
  const [uri, setUri] = useState<string | null>(null);
  useEffect(() => {
    if (!present) {
      setUri(null);
      return;
    }
    let alive = true;
    fetchCardImageObjectUrl(side).then((u) => alive && setUri(u));
    return () => {
      alive = false;
    };
  }, [side, present]);
  if (!present || !uri) return null;
  return (
    <Image source={{ uri }} resizeMode="cover" className="mb-2 h-24 w-full rounded-xl bg-inset" />
  );
}

function DisabledRow({ label }: { label: string }) {
  return (
    <View className="mb-2 flex-row items-center justify-between">
      <Text className="text-sm text-faint">{label}</Text>
      <View className="rounded-full bg-inset px-2 py-0.5">
        <Text className="text-[10px] font-semibold text-faint">Coming soon</Text>
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
    <PressableScale
      onPress={onPress}
      className="mb-1 -mx-2 flex-row items-center justify-between rounded-lg px-2 py-1.5 hover:bg-inset"
    >
      <Text className={tone === 'rose' ? 'text-body text-danger' : 'text-body text-primary'}>{label}</Text>
      <Text className="text-sm text-faint">›</Text>
    </PressableScale>
  );
}
