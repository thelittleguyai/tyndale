// Learn more: https://docs.expo.dev/guides/customizing-metro/
const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');

// getDefaultConfig auto-detects the monorepo workspace root (Expo SDK 49+),
// so workspace packages like @tyndale/shared resolve without extra config.
const config = getDefaultConfig(__dirname);

module.exports = withNativeWind(config, { input: './global.css' });
