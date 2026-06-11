import '../global.css';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, Text, View } from 'react-native';
import {
  useFonts,
  Inter_400Regular,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';

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

  return (
    <View className="flex-1 bg-navy-deep">
      {/* SCAFFOLD — not for real PHI — pinned to the top of every screen */}
      <View className="w-full bg-amber px-3 pb-1.5 pt-3">
        <Text className="text-center text-xs font-semibold text-ink">
          SCAFFOLD — not for real PHI
        </Text>
      </View>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: '#091621' },
        }}
      />
      <StatusBar style="light" />
    </View>
  );
}
