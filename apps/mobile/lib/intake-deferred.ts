/**
 * Session-scoped "intake deferred" flag (Save & exit escape hatch).
 *
 * The (app) layout gate redirects any user whose intake_status isn't 'complete'
 * back into the wizard. "Save & exit" sets this flag so a mid-intake user can
 * reach the dashboard for the rest of their session; it's cleared when intake
 * completes or on sign-out. Backed by sessionStorage on web (survives reloads,
 * dies with the tab) with an in-memory module fallback for native.
 */

const KEY = 'tyndale.intake_deferred';

let memoryFlag = false;

function webStorage(): Storage | null {
  try {
    if (typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined') {
      return window.sessionStorage;
    }
  } catch {
    // sessionStorage can throw (privacy mode / SSR) — fall through to memory.
  }
  return null;
}

export function setIntakeDeferred(): void {
  memoryFlag = true;
  try {
    webStorage()?.setItem(KEY, '1');
  } catch {
    // Quota/privacy errors — memory flag already set.
  }
}

export function isIntakeDeferred(): boolean {
  try {
    const s = webStorage();
    if (s) return s.getItem(KEY) === '1';
  } catch {
    // fall through to memory
  }
  return memoryFlag;
}

export function clearIntakeDeferred(): void {
  memoryFlag = false;
  try {
    webStorage()?.removeItem(KEY);
  } catch {
    // nothing to do — memory flag already cleared.
  }
}
