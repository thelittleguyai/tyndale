import * as SecureStore from 'expo-secure-store';

/**
 * Phase 1B auth scaffold for the Expo app — structure only, no real OAuth round
 * trip. Phase 2 wires expo-auth-session's Google flow and the SendGrid email
 * magic link. Apple Sign-In is deferred to the native iOS submission (fast-follow).
 */
export const googleAuthConfig = {
  // Per-platform OAuth client IDs for Expo (filled in Phase 2; see .env.example).
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

/** Email magic-link request — stub in Phase 1B; wires to SendGrid in Phase 2. */
export async function requestEmailMagicLink(_email: string): Promise<void> {
  // intentionally a no-op in Phase 1B
}
