'use client';

import { track } from '@/lib/analytics';
import { GoogleIcon } from '@/components/google-icon';

/**
 * Primary "Sign up with Google" CTA. Auth is not wired in Phase 1B — clicking
 * navigates to the /signin placeholder. We still fire the `signin_clicked`
 * Plausible event to establish a baseline.
 */
export function GoogleCta() {
  return (
    <a
      href="/signin"
      onClick={() => track('signin_clicked')}
      className="inline-flex items-center gap-3 rounded-lg bg-white px-5 py-3 text-[15px] font-semibold text-ink shadow-sm transition hover:bg-white/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-[#2C4D52]"
    >
      <GoogleIcon size={18} />
      Sign up with Google
    </a>
  );
}
