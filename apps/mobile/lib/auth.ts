/**
 * Mobile auth helpers (Phase 2K).
 *
 * Session is cookie-based on web (the runtime sets an HttpOnly cookie). On
 * native, expo-secure-store holds a copy of the session token for deep-link
 * return flows. useCurrentUser loads /v1/auth/session; useSignOut clears both.
 */

import { useCallback, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';

import {
  getAuthSession,
  logout as apiLogout,
  requestMagicLink,
  type UserProfile,
} from './api-client';

export const googleAuthConfig = {
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
  androidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID,
} as const;

const SESSION_KEY = 'tyndale.session';

export async function storeSessionToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(SESSION_KEY, token);
}
export async function getSessionToken(): Promise<string | null> {
  return SecureStore.getItemAsync(SESSION_KEY);
}
export async function clearSessionToken(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}

/** Email magic-link request (real in Phase 2K). */
export async function requestEmailMagicLink(email: string, returnUrl?: string): Promise<void> {
  await requestMagicLink(email, returnUrl);
}

export interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/** Loads the current session on mount. Returns {user, loading, refresh}. */
export function useCurrentUser(): AuthState {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const s = await getAuthSession();
      setUser(s.user);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { user, loading, refresh };
}

/** Returns a signOut() that clears the server cookie + local token. */
export function useSignOut(): () => Promise<void> {
  return useCallback(async () => {
    await apiLogout();
    await clearSessionToken();
  }, []);
}
