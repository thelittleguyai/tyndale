/**
 * The branded not-found screen (2026-09-23 minor) — replaces Expo Router's default "Unmatched
 * Route" page. Renders before any sign-in; its words are registry copy from the `app` copy
 * surface, with a plain client fallback if the fetch fails (never a blank page, never Expo's).
 */
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Link, Stack } from 'expo-router';

import { getSurfaceCopy, type SurfaceCopy } from '../lib/api-client';

const FALLBACK = {
  not_found_title: "That page isn't here.",
  not_found_body: 'The link may be old, or the address has a typo.',
  not_found_cta: 'Go to my home screen',
};

export default function NotFoundScreen() {
  const [copy, setCopy] = useState<SurfaceCopy>({});
  useEffect(() => {
    let alive = true;
    getSurfaceCopy('app')
      .then((c) => {
        if (alive) setCopy(c);
      })
      .catch(() => {
        /* the fallback renders */
      });
    return () => {
      alive = false;
    };
  }, []);
  return (
    <View className="flex-1 items-center justify-center bg-page px-6" testID="not-found">
      <Stack.Screen options={{ title: copy.not_found_title || FALLBACK.not_found_title }} />
      <View className="w-full max-w-md rounded-2xl border border-hairline bg-surface p-6 shadow-card">
        <Text accessibilityRole="header" className="text-2xl font-bold text-primary">
          {copy.not_found_title || FALLBACK.not_found_title}
        </Text>
        <Text className="mt-3 text-body leading-6 text-secondary">
          {copy.not_found_body || FALLBACK.not_found_body}
        </Text>
        <Link href="/" asChild>
          <Text
            accessibilityRole="link"
            className="mt-6 min-h-[44px] overflow-hidden rounded-xl bg-accent px-4 py-3 text-center text-body font-bold text-on-accent"
            testID="not-found-home"
          >
            {copy.not_found_cta || FALLBACK.not_found_cta}
          </Text>
        </Link>
      </View>
    </View>
  );
}
