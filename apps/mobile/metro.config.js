// Learn more: https://docs.expo.dev/guides/customizing-metro/
const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');
const path = require('path');

// getDefaultConfig auto-detects the monorepo workspace root (Expo SDK 49+),
// so workspace packages like @tyndale/shared resolve without extra config.
const config = getDefaultConfig(__dirname);

const nwConfig = withNativeWind(config, { input: './global.css' });

// --- Dedupe React across the monorepo (DL-44) ------------------------------
// apps/mobile pins react 19.0.0 (Expo SDK 53) while apps/web-marketing's deps
// float react to 19.2.x, which npm hoists to the workspace root — so npm keeps
// TWO physical React copies. Metro would bundle BOTH -> two React instances ->
// a null hook dispatcher -> the web app white-screens on the first useState.
// Force every react / react-dom import (incl. subpaths like react/jsx-runtime)
// to resolve from the workspace root so the bundle contains exactly one React.
//
// Why here and not in npm: a pre-existing peer conflict (react-native-worklets
// wants RN 0.83-0.86 vs our 0.79.6) makes a clean `npm install` ERESOLVE, so a
// dependency-tree dedupe isn't viable. This bundler-level alias is the
// documented Expo-monorepo approach and touches no dependencies.
const workspaceRoot = path.resolve(__dirname, '../..');
const resolveFrom = path.join(workspaceRoot, 'package.json'); // existing file; only its dir is used
const DEDUPE = ['react', 'react-dom'];
const upstreamResolve = nwConfig.resolver.resolveRequest;

nwConfig.resolver.resolveRequest = (context, moduleName, platform) => {
  const resolve = upstreamResolve ?? context.resolveRequest;
  if (DEDUPE.some((m) => moduleName === m || moduleName.startsWith(`${m}/`))) {
    return resolve({ ...context, originModulePath: resolveFrom }, moduleName, platform);
  }
  return resolve(context, moduleName, platform);
};

module.exports = nwConfig;
