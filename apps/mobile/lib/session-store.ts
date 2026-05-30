/**
 * Native (iOS/Android) session-token store — backed by expo-secure-store.
 *
 * The web build resolves session-store.web.ts instead (Metro platform
 * extensions), so expo-secure-store is NEVER bundled for web — importing it on
 * web throws at module-eval and white-screens the whole app.
 */
import * as SecureStore from 'expo-secure-store';

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
