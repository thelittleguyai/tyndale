import { handlers } from '@/lib/auth';

// Auth.js v5 route handlers. Providers are conditional on env (see src/lib/auth.ts);
// with none configured (Phase 1B default), these endpoints exist but no provider
// flow is active.
export const { GET, POST } = handlers;
