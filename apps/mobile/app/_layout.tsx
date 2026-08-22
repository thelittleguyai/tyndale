import '../global.css';
import { Stack } from 'expo-router';
import Head from 'expo-router/head';
import { StatusBar } from 'expo-status-bar';
import { Platform, Text, View } from 'react-native';
import {
  useFonts,
  Inter_400Regular,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';

import { light, dark } from '../theme/tokens';
import { useThemeController } from '../theme/useTheme';

// Native default font. Web gets Inter via global.css (html/body + #root
// inherit); native <Text> needs an explicit family, so default every Text to
// the expo-loaded face. defaultProps isn't in RN's types — hence `as any` —
// but remains the pragmatic way to set an app-wide Text default.
if (Platform.OS !== 'web') {
  const TextAny = Text as any;
  TextAny.defaultProps = TextAny.defaultProps ?? {};
  TextAny.defaultProps.style = [
    { fontFamily: 'Inter_400Regular' },
    TextAny.defaultProps.style,
  ];
}

export default function RootLayout() {
  // Load Inter. We render regardless of load state so a font hiccup never blanks
  // the app; text falls back to the system font until Inter is ready.
  useFonts({ Inter_400Regular, Inter_600SemiBold, Inter_700Bold });

  // Apply the persisted theme mode ("Clear day" default; "Midnight ledger" when chosen).
  const { resolved } = useThemeController();
  const pageBg = resolved === 'dark' ? dark.bg.page : light.bg.page;

  return (
    <View className="flex-1 bg-page">
      {/* The browser tab: a real title (the export used to emit an empty managed <title>, so
          tabs showed the bare URL). Route screens can override with their own <Head>. */}
      <Head>
        <title>Tyndale</title>
      </Head>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: pageBg },
        }}
      />
      {/* Light mode wants dark status-bar glyphs; dark mode wants light. */}
      <StatusBar style={resolved === 'dark' ? 'light' : 'dark'} />
    </View>
  );
}
