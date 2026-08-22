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

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Platform,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SvgXml } from 'react-native-svg';

import { logoSvg } from '@tyndale/shared';

import { track } from '../../lib/analytics';
import { getGoogleAuthUrl } from '../../lib/api-client';
import { requestEmailMagicLink } from '../../lib/auth';
import { PressableScale } from '../../components/ui/PressableScale';
import { ScreenView } from '../../components/ui/Screen';
import { useThemeColors } from '../../theme/useThemeColors';

/**
 * Google consent-URL prefetch (2026-08-22, item 2). SAFE per runtime/app/routes/auth.py:
 * POST /v1/auth/login mints a state + sets the state cookie with max_age=600; the state is
 * only COMPARED at the callback (constant-time) and deleted there — never consumed at mint —
 * and a second /auth/login simply overwrites the cookie. So a URL fetched on mount stays
 * valid for 10 minutes; we treat it as fresh for 9 and re-fetch past that (or if the
 * prefetch failed), always using the MOST RECENT url so it matches the current cookie.
 */
const PREFETCH_FRESH_MS = 9 * 60 * 1000;

type Prefetched = { url: string; at: number };

/** One automatic retry on a failed URL fetch (cold start, flaky network), then throw. */
async function fetchAuthUrlWithRetry(): Promise<string> {
  try {
    return await getGoogleAuthUrl();
  } catch {
    return await getGoogleAuthUrl();
  }
}

export default function SignInScreen() {
  const c = useThemeColors();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [focused, setFocused] = useState(false);
  const prefetchRef = useRef<Prefetched | null>(null);
  const inflightRef = useRef<Promise<string> | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  // Prefetch on mount so the click is a pure redirect. A failure here is silent — the
  // click path re-fetches (with its own retry) and reports errors on its own.
  const prefetch = useCallback(() => {
    const p = fetchAuthUrlWithRetry()
      .then((url) => {
        prefetchRef.current = { url, at: Date.now() };
        return url;
      })
      .finally(() => {
        if (inflightRef.current === p) inflightRef.current = null;
      });
    inflightRef.current = p;
    p.catch(() => undefined);
    return p;
  }, []);

  useEffect(() => {
    prefetch();
  }, [prefetch]);

  const resolveAuthUrl = async (): Promise<string> => {
    const cached = prefetchRef.current;
    if (cached && Date.now() - cached.at < PREFETCH_FRESH_MS) return cached.url;
    if (inflightRef.current) return inflightRef.current; // a (re)fetch is already running
    return prefetch(); // expired, or the prefetch failed → re-fetch (with retry)
  };

  const onGoogle = async () => {
    if (googleBusy) return;
    track('signin_clicked', { method: 'google' });
    setError(null);
    setGoogleBusy(true); // instant feedback, before any network
    try {
      const url = await resolveAuthUrl();
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.assign(url);
        // Stay busy — the page is navigating away.
      } else {
        await Linking.openURL(url);
        setGoogleBusy(false);
      }
    } catch (e: any) {
      prefetchRef.current = null;
      setGoogleBusy(false);
      setError(
        e?.message
          ? `Could not start Google sign-in (${e.message}). Tap to try again.`
          : 'Could not start Google sign-in. Tap to try again.',
      );
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
            accessibilityState={{ busy: googleBusy, disabled: googleBusy }}
            onPress={onGoogle}
            disabled={googleBusy}
            testID="google-signin"
            className="min-h-[48px] w-full flex-row items-center justify-center gap-2 rounded-xl border border-hairline bg-surface px-5 py-3 hover:bg-inset"
          >
            {googleBusy ? (
              <ActivityIndicator size="small" color={c.accent} testID="google-spinner" />
            ) : null}
            <Text className="text-base font-semibold text-primary">
              {googleBusy ? 'Opening Google…' : 'Continue with Google'}
            </Text>
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
