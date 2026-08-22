/**
 * Sign-in screen (Phase 2K; design pass 2026-08-22).
 *
 * Continue with Google → POST /v1/auth/login → open the returned consent URL
 * (window redirect on web; system browser on native). Continue with email →
 * POST /v1/auth/magic-link-request → "check your email" state with 60s resend.
 *
 * Every colour is a token (light + dark via the semantic slots); the Google button is the
 * system's SECONDARY button (surface + hairline + primary text — the old text-on-accent on a
 * surface button was a contrast bug); the primary action is accent teal; the disabled send
 * state uses text-secondary on inset (5.5:1 light / 6.9:1 dark — text-faint measured 4.24:1
 * on light, below AA); placeholders use the theme-aware faint token (the old
 * rgba(255,255,255,0.35) was a dark-theme leftover, invisible on light). Web focus rings come
 * from global.css (:focus-visible → accent outline), never the browser default blue.
 */

import { useEffect, useState } from 'react';
import { Linking, Platform, Pressable, Text, TextInput, View } from 'react-native';
import { SvgXml } from 'react-native-svg';

import { logoSvg } from '@tyndale/shared';

import { track } from '../../lib/analytics';
import { getGoogleAuthUrl } from '../../lib/api-client';
import { requestEmailMagicLink } from '../../lib/auth';
import { PressableScale } from '../../components/ui/PressableScale';
import { ScreenView } from '../../components/ui/Screen';
import { useThemeColors } from '../../theme/useThemeColors';

export default function SignInScreen() {
  const c = useThemeColors();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const onGoogle = async () => {
    track('signin_clicked', { method: 'google' });
    setError(null);
    try {
      const url = await getGoogleAuthUrl();
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.assign(url);
      } else {
        await Linking.openURL(url);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Could not start Google sign-in.');
    }
  };

  const onEmail = async () => {
    if (!email.trim() || busy || cooldown > 0) return;
    track('signin_clicked', { method: 'email' });
    setBusy(true);
    setError(null);
    try {
      await requestEmailMagicLink(email.trim());
      setSent(true);
      setCooldown(60);
    } catch (e: any) {
      setError(e?.message ?? 'Could not send the link.');
    } finally {
      setBusy(false);
    }
  };

  const canSend = !!email.trim() && !busy;

  return (
    <View className="flex-1 items-center justify-center bg-page px-6 py-10">
      <ScreenView className="w-full max-w-sm items-center">
        <View className="mb-5 rounded-full bg-inset p-2">
          <SvgXml xml={logoSvg} width={56} height={56} />
        </View>
        <Text className="text-2xl font-bold tracking-tight text-primary">Sign in to Tyndale</Text>
        <Text className="mt-2 text-center text-body leading-6 text-secondary">
          Your medical bill advocate. Check a bill, or pick up where you left off.
        </Text>

        {/* Card: the same surface / hairline / radius rhythm as settings + landing cards. */}
        <View className="mt-8 w-full rounded-2xl border border-hairline bg-surface p-5 shadow-card">
          <PressableScale
            accessibilityRole="button"
            onPress={onGoogle}
            testID="google-signin"
            className="min-h-[48px] w-full flex-row items-center justify-center gap-2 rounded-xl border border-hairline bg-surface px-5 py-3 hover:bg-inset"
          >
            <Text className="text-base font-semibold text-primary">Continue with Google</Text>
          </PressableScale>

          <View className="my-5 flex-row items-center gap-3">
            <View className="h-0 flex-1 border-t border-hairline" />
            <Text className="text-xs text-faint">Or sign in with email</Text>
            <View className="h-0 flex-1 border-t border-hairline" />
          </View>

          {sent ? (
            <View className="items-center">
              <Text className="text-center text-body leading-6 text-primary">
                Check your email — we sent a sign-in link to{' '}
                <Text className="font-semibold">{email}</Text>.
              </Text>
              <Pressable
                onPress={onEmail}
                disabled={cooldown > 0}
                accessibilityRole="button"
                className="mt-3 min-h-[44px] justify-center px-3 active:opacity-70"
              >
                <Text
                  className={
                    cooldown > 0 ? 'text-sm text-faint' : 'text-sm font-semibold text-accent'
                  }
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend link'}
                </Text>
              </Pressable>
            </View>
          ) : (
            <View>
              <Text className="mb-1.5 text-sm text-secondary">Email</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                onSubmitEditing={onEmail}
                placeholder="you@example.com"
                placeholderTextColor={c.text.faint}
                autoCapitalize="none"
                autoComplete="email"
                keyboardType="email-address"
                returnKeyType="send"
                accessibilityLabel="Email address"
                className={`min-h-[48px] rounded-xl border bg-inset px-4 py-3 text-base text-primary ${
                  focused ? 'border-accent' : 'border-hairline'
                }`}
              />
              <PressableScale
                onPress={onEmail}
                disabled={!canSend}
                accessibilityRole="button"
                accessibilityState={{ disabled: !canSend }}
                testID="send-magic-link"
                className={
                  canSend
                    ? 'mt-3 min-h-[48px] items-center justify-center rounded-xl bg-accent px-5 py-3 hover:bg-accent'
                    : 'mt-3 min-h-[48px] items-center justify-center rounded-xl bg-inset px-5 py-3'
                }
              >
                <Text
                  className={
                    canSend
                      ? 'text-base font-bold text-on-accent'
                      : 'text-base font-semibold text-secondary'
                  }
                >
                  {busy ? 'Sending…' : 'Send magic link'}
                </Text>
              </PressableScale>
            </View>
          )}

          {error ? (
            <Text className="mt-4 text-sm leading-5 text-danger" accessibilityRole="alert">
              {error}
            </Text>
          ) : null}
        </View>

        <Text className="mt-8 max-w-xs text-center text-xs leading-4 text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
          advice.
        </Text>
      </ScreenView>
    </View>
  );
}
