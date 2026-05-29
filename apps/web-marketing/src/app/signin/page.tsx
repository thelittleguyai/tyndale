'use client';

/**
 * Sign-in (Phase 2K) — calls the runtime's /v1/auth/* endpoints.
 *
 * Continue with Google → POST /v1/auth/login → redirect to the consent URL.
 * Email → POST /v1/auth/magic-link-request → "check your email" + 60s resend.
 *
 * RUNTIME base comes from NEXT_PUBLIC_RUNTIME_URL (same-origin /v1 by default,
 * assuming an ingress/proxy fronts the runtime under tyndaleapp.net). Cookies
 * ride with credentials:'include'.
 */

import { useEffect, useState } from 'react';

import { Logo, Wordmark } from '@/components/logo';

const RUNTIME = process.env.NEXT_PUBLIC_RUNTIME_URL ?? '';

export default function SignInPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const onGoogle = async () => {
    setError(null);
    try {
      const res = await fetch(`${RUNTIME}/v1/auth/login`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`login init failed: ${res.status}`);
      const { authorization_url } = (await res.json()) as { authorization_url: string };
      window.location.assign(authorization_url);
    } catch {
      setError('Could not start Google sign-in. Please try again.');
    }
  };

  const onEmail = async () => {
    if (!email.trim() || busy || cooldown > 0) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${RUNTIME}/v1/auth/magic-link-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim() }),
      });
      if (res.status === 429) {
        const retry = res.headers.get('Retry-After');
        throw new Error(`Too many requests — try again in ${retry ?? 'a few'} seconds.`);
      }
      if (!res.ok) throw new Error('Could not send the link.');
      setSent(true);
      setCooldown(60);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not send the link.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center bg-cream px-6">
      <div className="flex items-center gap-2.5 text-ink">
        <Logo size={36} />
        <Wordmark />
      </div>
      <h1 className="mt-8 text-2xl font-bold tracking-tight text-ink">Sign in</h1>

      <div className="mt-6 w-full max-w-sm">
        <button
          onClick={onGoogle}
          className="w-full rounded-md border border-border bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-cream-soft"
        >
          Continue with Google
        </button>

        <div className="my-5 text-center text-xs uppercase tracking-widest text-ink/40">
          or sign in with email
        </div>

        {sent ? (
          <div className="text-center">
            <p className="text-sm leading-6 text-teal-deep">
              Check your email — we sent a sign-in link to {email}.
            </p>
            <button
              onClick={onEmail}
              disabled={cooldown > 0}
              className="mt-3 text-xs font-semibold text-teal disabled:text-ink/40"
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend link'}
            </button>
          </div>
        ) : (
          <>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-md border border-border bg-white px-4 py-3 text-sm text-ink"
            />
            <button
              onClick={onEmail}
              disabled={busy || !email.trim()}
              className="mt-3 w-full rounded-md bg-teal px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal-deep disabled:opacity-50"
            >
              {busy ? 'Sending…' : 'Send magic link'}
            </button>
          </>
        )}

        {error ? <p className="mt-4 text-center text-sm text-rose">{error}</p> : null}
      </div>

      <p className="mt-10 max-w-sm text-center text-xs text-ink/50">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
        advice.
      </p>
    </main>
  );
}
