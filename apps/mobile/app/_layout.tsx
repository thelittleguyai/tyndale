import '../global.css';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Text, View } from 'react-native';
import {
  useFonts,
  Inter_400Regular,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';

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
