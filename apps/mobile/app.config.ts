import type { ExpoConfig } from 'expo/config';

const config: ExpoConfig = {
  name: 'Tyndale',
  slug: 'tyndale',
  scheme: 'tyndale',
  version: '0.0.0',
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  newArchEnabled: true,
  ios: {
    bundleIdentifier: 'net.tyndaleapp.app',
    supportsTablet: true,
    // NOTE: Apple Sign-In capability is deferred to the native iOS App Store
    // submission (fast-follow per the locked decision) — not wired in Phase 1B.
  },
  android: {
    package: 'net.tyndaleapp.app',
  },
  web: {
    bundler: 'metro',
    output: 'static',
    // Tab + home-screen icon (generated from the shared logo SVG into public/). The static
    // HTML root (app/+html.tsx) links the full icon set; this is Expo's own favicon hook.
    favicon: './public/favicon-32.png',
  },
  plugins: [
    'expo-router',
    'expo-font',
    'expo-secure-store',
    'expo-web-browser',
    // N1 native capture — the permission string states the honest, narrow purpose.
    [
      'expo-camera',
      { cameraPermission: 'Tyndale uses the camera only to photograph your bills and documents.' },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
