import NextAuth from 'next-auth';
import type { NextAuthConfig } from 'next-auth';
import Google from 'next-auth/providers/google';

/**
 * Auth.js v5 scaffold. Phase 1B only makes the structure exist — real end-to-end
 * auth wiring lands in Phase 2 (after the runtime exists for callbacks).
 *
 * - Google: enabled only when GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET are present.
 * - Email (SendGrid magic links): scaffolded but inactive in Phase 1B (wires Phase 2).
 * - Apple: intentionally NOT wired — fast-follow at native iOS App Store submission.
 * - Sessions: JWT strategy for now; move to DB sessions in Phase 4.
 */
const providers: NextAuthConfig['providers'] = [];

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  );
}

// Email (SendGrid) magic-link provider is intentionally left unwired in Phase 1B.
// Phase 2 adds it here, e.g. an HTTP/Nodemailer provider pointed at SendGrid.

if (process.env.NODE_ENV !== 'production' && !process.env.AUTH_SECRET) {
  // eslint-disable-next-line no-console
  console.warn(
    '[auth] AUTH_SECRET is not set. Fine for Phase 1B local dev; REQUIRED in production.',
  );
}

const config: NextAuthConfig = {
  providers,
  session: { strategy: 'jwt' },
  pages: { signIn: '/signin' },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
