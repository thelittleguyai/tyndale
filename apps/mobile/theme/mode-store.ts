/**
 * Persisted theme-mode preference (light / dark / system). Default is 'light' ("Clear day") when
 * nothing is stored. Backed by localStorage on web (survives across sessions) with an in-memory
 * fallback on native / private mode — same pattern as lib/intake-deferred.ts.
 */
import type { ThemeMode } from './tokens';

const KEY = 'tyndale.theme_mode';
let memory: ThemeMode = 'light';

function localStore(): Storage | null {
  try {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      return window.localStorage;
    }
  } catch {
    // localStorage can throw (privacy mode / SSR) — fall through to memory.
  }
  return null;
}

export function loadThemeMode(): ThemeMode {
  const v = localStore()?.getItem(KEY) ?? memory;
  return v === 'dark' || v === 'system' || v === 'light' ? v : 'light';
}

export function saveThemeMode(mode: ThemeMode): void {
  memory = mode;
  try {
    localStore()?.setItem(KEY, mode);
  } catch {
    // best-effort; memory fallback already set
  }
}
