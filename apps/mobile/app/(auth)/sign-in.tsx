/**
 * Sign-in screen (Phase 2K).
 *
 * Continue with Google → POST /v1/auth/login → open the returned consent URL
 * (window redirect on web; system browser on native). Continue with email →
 * POST /v1/auth/magic-link-request → "check your email" state with 60s resend.
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

export default function SignInScreen() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

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

  return (
    <View className="flex-1 items-center justify-center bg-navy-deep px-6">
      <ScreenView className="items-center">
        <View className="mb-5 rounded-full bg-cream p-2">
          <SvgXml xml={logoSvg} width={56} height={56} />
        </View>
        <Text className="text-2xl font-bold text-white">Sign in to Tyndale</Text>

        <PressableScale
          accessibilityRole="button"
          onPress={onGoogle}
          className="mt-8 w-full max-w-xs items-center rounded-md bg-white px-6 py-3 shadow-card hover:bg-cream-soft"
        >
          <Text className="text-base font-semibold text-ink">Continue with Google</Text>
        </PressableScale>

        <Text className="my-5 text-xs uppercase tracking-widest text-white/40">
          or sign in with email
        </Text>

        {sent ? (
          <View className="w-full max-w-xs items-center">
            <Text className="text-center text-sm leading-6 text-sage">
              Check your email — we sent a sign-in link to {email}.
            </Text>
            <Pressable
              onPress={onEmail}
              disabled={cooldown > 0}
              className="mt-4 active:opacity-70"
            >
              <Text
                className={
                  cooldown > 0 ? 'text-xs text-white/40' : 'text-xs font-semibold text-sage'
                }
              >
                {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend link'}
              </Text>
            </Pressable>
          </View>
        ) : (
          <View className="w-full max-w-xs">
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor="rgba(255,255,255,0.35)"
              autoCapitalize="none"
              keyboardType="email-address"
              className="rounded-md border border-white/20 bg-white/5 px-4 py-3 text-base text-white"
            />
            <PressableScale
              onPress={onEmail}
              disabled={busy || !email.trim()}
              className={
                busy || !email.trim()
                  ? 'mt-3 items-center rounded-md bg-white/10 px-6 py-3'
                  : 'mt-3 items-center rounded-md bg-sage px-6 py-3 shadow-card hover:bg-sage-deep'
              }
            >
              <Text
                className={
                  busy || !email.trim()
                    ? 'text-base font-semibold text-white/50'
                    : 'text-base font-bold text-ink'
                }
              >
                {busy ? 'Sending…' : 'Send magic link'}
              </Text>
            </PressableScale>
          </View>
        )}

        {error ? <Text className="mt-5 text-sm text-rose">{error}</Text> : null}

        <Text className="mt-10 max-w-xs text-center text-xs text-white/40">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
          advice.
        </Text>
      </ScreenView>
    </View>
  );
}
