/**
 * Theme controller — applies the persisted mode on mount and exposes a setter. NativeWind's
 * colorScheme is a global store, so calling this from the root (to apply on load) and from
 * Settings (to change it) needs no context; both stay in sync through NativeWind + mode-store.
 *
 * 'system' follows the OS scheme; 'light'/'dark' force it. Default is 'light' when unset.
 */
import { useEffect, useState } from 'react';
import { useColorScheme } from 'nativewind';

import { loadThemeMode, saveThemeMode } from './mode-store';
import type { ThemeMode } from './tokens';

export function useThemeController() {
  const { colorScheme, setColorScheme } = useColorScheme();
  const [mode, setMode] = useState<ThemeMode>('light');

  useEffect(() => {
    const stored = loadThemeMode();
    setMode(stored);
    setColorScheme(stored); // 'system' | 'light' | 'dark'
  }, [setColorScheme]);

  const changeMode = (next: ThemeMode) => {
    setMode(next);
    saveThemeMode(next);
    setColorScheme(next);
  };

  // `colorScheme` is the RESOLVED scheme ('light' | 'dark'); default to light before it settles.
  return { mode, resolved: (colorScheme ?? 'light') as 'light' | 'dark', setMode: changeMode };
}
