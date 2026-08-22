'use client';

/**
 * Post-auth landing (Phase 2K; interstitial 2026-08-22). Both OAuth callback and the
 * magic-link verify redirect here after the runtime sets the session cookie. Previously the
 * page sat on "Signing you in…" until a session check resolved and then waited for a click.
 * Now it is an explicit INTERSTITIAL: a spinner while the session is confirmed, then an
 * automatic continue into the app (the button stays as the manual fallback, and is the only
 * path when the session check fails — never a dead end).
 */

import { useEffect, useState } from 'react';

import { Logo, Wordmark } from '@/components/logo';

const RUNTIME = process.env.NEXT_PUBLIC_RUNTIME_URL ?? '';
const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? 'https://app.tyndaleapp.net';
const AUTO_CONTINUE_MS = 900;

type Phase = 'checking' | 'ok' | 'unknown';

export default function SignedInPage() {
  const [name, setName] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('checking');

  useEffect(() => {
    let alive = true;
    fetch(`${RUNTIME}/v1/auth/session`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive) return;
        if (d?.user) {
          setName(d.user.first_name ?? null);
          setPhase('ok');
        } else {
          setPhase('unknown');
        }
      })
      .catch(() => alive && setPhase('unknown'));
    return () => {
      alive = false;
    };
  }, []);

  // Confirmed session → continue into the app on its own; the button remains for anyone
  // who reads faster than the timer.
  useEffect(() => {
    if (phase !== 'ok') return;
    const t = setTimeout(() => window.location.replace(APP_URL), AUTO_CONTINUE_MS);
    return () => clearTimeout(t);
  }, [phase]);

  const headline =
    phase === 'checking'
      ? 'Signing you in…'
      : phase === 'ok'
        ? name
          ? `You're signed in, ${name}.`
          : 'You’re signed in.'
        : 'Welcome back.';

  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center bg-cream px-6 text-center">
      <div className="flex items-center gap-2.5 text-ink">
        <Logo size={36} />
        <Wordmark />
      </div>
      {phase !== 'unknown' ? (
        <span
          role="status"
          aria-live="polite"
          className="mt-8 inline-block h-8 w-8 animate-spin rounded-full border-[3px] border-teal/25 border-t-teal"
        />
      ) : null}
      <h1 className="mt-5 text-2xl font-bold tracking-tight text-ink">{headline}</h1>
      <p className="mt-3 max-w-md text-ink/70">
        {phase === 'ok'
          ? 'Taking you to your dashboard.'
          : phase === 'checking'
            ? 'Confirming your session — this takes a moment on the first visit.'
            : 'Continue to your Tyndale dashboard to upload a bill or check where your open issues stand.'}
      </p>
      <a
        href={APP_URL}
        className="mt-8 inline-flex min-h-[44px] items-center rounded-md bg-teal px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-teal/60 focus-visible:ring-offset-2"
      >
        Go to my dashboard →
      </a>
    </main>
  );
}
