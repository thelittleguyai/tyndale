import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Edge gate (Phase CO-6A). The runtime owns the session (HS256 cookie signed
 * with the RUNTIME's secret — not this app's AUTH_SECRET), so middleware can't
 * cryptographically validate it here. It does a presence check and bounces
 * anonymous visitors to the real sign-in (the runtime auth flow at dev.).
 *
 * The AUTHORITATIVE controls are elsewhere and do NOT depend on this:
 *   - network layer: the Container Apps ingress IP allowlist (DL-60, infra/)
 *   - app layer: every /v1/admin/* route 404s non-admins; the client guard
 *     (useRequireAdmin) renders a 404 shell when those calls fail.
 */

// Sign-in URL comes from env (no hardcoded dev./admin. host). Production must set it;
// local dev falls back to the dev host.
function resolveSignInUrl(): string {
  const url = process.env.NEXT_PUBLIC_SIGNIN_URL;
  if (url) return url;
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'NEXT_PUBLIC_SIGNIN_URL is not set. Set it to the member sign-in URL, e.g. https://app.tyndaleapp.net/sign-in.',
    );
  }
  return 'https://dev.tyndaleapp.net/signin';
}

const SIGNIN_URL = resolveSignInUrl();
const SESSION_COOKIES = ['__Secure-tyndale_session', 'tyndale_session'];

export function middleware(req: NextRequest) {
  const hasSession = SESSION_COOKIES.some((name) => req.cookies.has(name));
  if (!hasSession) {
    return NextResponse.redirect(new URL(SIGNIN_URL));
  }
  return NextResponse.next();
}

export const config = {
  // Run on everything except Next internals + the NextAuth handler.
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/auth).*)'],
};
