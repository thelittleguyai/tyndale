'use client';

/**
 * Post-auth landing (Phase 2K). Confirms the session established by the
 * runtime (cookie set on /v1/auth/callback or magic-link-verify) and points
 * the user at the app dashboard. The mobile app lives at a subdomain that
 * shares the .tyndaleapp.net cookie.
 */

import { useEffect, useState } from 'react';

import { Logo, Wordmark } from '@/components/logo';

const RUNTIME = process.env.NEXT_PUBLIC_RUNTIME_URL ?? '';
const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? 'https://app.tyndaleapp.net';

export default function SignedInPage() {
  const [name, setName] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    fetch(`${RUNTIME}/v1/auth/session`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { user: null }))
      .then((d) => setName(d?.user?.first_name ?? null))
      .catch(() => setName(null))
      .finally(() => setChecked(true));
  }, []);

  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center bg-cream px-6 text-center">
      <div className="flex items-center gap-2.5 text-ink">
        <Logo size={36} />
        <Wordmark />
      </div>
      <h1 className="mt-8 text-2xl font-bold tracking-tight text-ink">
        {name ? `You're signed in, ${name}.` : checked ? 'Welcome back.' : 'Signing you in…'}
      </h1>
      <p className="mt-3 max-w-md text-ink/70">
        Continue to your Tyndale dashboard to upload a bill or check where your open issues stand.
      </p>
      <a
        href={APP_URL}
        className="mt-8 inline-flex min-h-[44px] items-center rounded-md bg-teal px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-deep"
      >
        Go to my dashboard →
      </a>
    </main>
  );
}
