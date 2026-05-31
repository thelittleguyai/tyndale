import NextAuth from 'next-auth';
import type { NextAuthConfig } from 'next-auth';
import Google from 'next-auth/providers/google';

// Mirrors apps/web-marketing/src/lib/auth.ts. The authoritative session is the
// RUNTIME's .tyndaleapp.net cookie (Phase 2K); this NextAuth config exists for
// the sign-in handoff + parity with the marketing app. Real admin gating is
// server-side (runtime /v1/admin/* → 404 for non-admins, DL-60) + the network
// IP allowlist; see src/middleware.ts + src/lib/use-admin.ts.

const providers: NextAuthConfig['providers'] = [];

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  );
}

if (process.env.NODE_ENV !== 'production' && !process.env.AUTH_SECRET) {
  console.warn('[auth] AUTH_SECRET is not set. Fine for local dev; REQUIRED in production.');
}

const config: NextAuthConfig = {
  providers,
  session: { strategy: 'jwt' },
  pages: { signIn: '/signin' },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
