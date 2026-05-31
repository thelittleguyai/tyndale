'use client';

import { useEffect, useState } from 'react';

import { AdminApiError, adminGetDashboard } from './api-client';

type AdminGuard = { checking: boolean; allowed: boolean };

/**
 * Client-side admin probe. The runtime is the authority: GET /v1/admin/dashboard
 * returns 200 for an admin and 404 for anyone else (anti-enumeration, DL-60).
 * So a successful call == admin. Non-admin / unauthenticated → not allowed, and
 * the caller renders a plain 404 (never reveals the console exists).
 */
export function useRequireAdmin(): AdminGuard {
  const [state, setState] = useState<AdminGuard>({ checking: true, allowed: false });

  useEffect(() => {
    let alive = true;
    adminGetDashboard()
      .then(() => alive && setState({ checking: false, allowed: true }))
      .catch((e: unknown) => {
        if (!alive) return;
        // 404/401/403 → not an admin (or not signed in). Anything else → also deny.
        void (e instanceof AdminApiError);
        setState({ checking: false, allowed: false });
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
