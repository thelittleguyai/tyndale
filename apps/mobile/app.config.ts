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
  },
  plugins: ['expo-router', 'expo-font', 'expo-secure-store', 'expo-web-browser'],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
