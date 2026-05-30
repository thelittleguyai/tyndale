/**
 * Web session-token store. On web the real session is the runtime's HttpOnly
 * cookie on .tyndaleapp.net (not readable from JS), so this is a thin
 * localStorage shim that exists only so the shared auth module compiles and the
 * native deep-link API has a web counterpart.
 *
 * Crucially this file does NOT import expo-secure-store — that module is
 * unavailable on web and throws at module-eval, which would blank the app.
 */
const SESSION_KEY = 'tyndale.session';

export async function storeSessionToken(token: string): Promise<void> {
  try {
    globalThis.localStorage?.setItem(SESSION_KEY, token);
  } catch {
    /* storage unavailable (SSR/static prerender) — ignore */
  }
}
export async function getSessionToken(): Promise<string | null> {
  try {
    return globalThis.localStorage?.getItem(SESSION_KEY) ?? null;
  } catch {
    return null;
  }
}
export async function clearSessionToken(): Promise<void> {
  try {
    globalThis.localStorage?.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}
