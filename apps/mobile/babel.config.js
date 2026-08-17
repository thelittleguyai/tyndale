module.exports = function (api) {
  // Cache keyed on NODE_ENV so the test branch (no NativeWind) and the app
  // branch (with NativeWind) are each cached correctly.
  api.cache.using(() => process.env.NODE_ENV);
  const isTest = api.env('test');
  return {
    presets: [
      // In jest, drop NativeWind's jsxImportSource + babel plugin so className
      // becomes an ignored prop and components render without the css-interop
      // runtime. Tests assert behavior, not styles. The app build keeps NativeWind.
      ['babel-preset-expo', isTest ? {} : { jsxImportSource: 'nativewind' }],
      ...(isTest ? [] : [nativewindPreset]),
    ],
  };
};

// nativewind/babel (= react-native-css-interop/babel) hardcodes
// 'react-native-worklets/plugin' in its plugin list — that, not any import of ours,
// is why react-native-worklets was ever a dependency. DL-44 removed it (its peer
// conflict blocked every Expo native install), and nothing here uses reanimated or
// animated/transition classes, so this reproduces the preset minus that one line.
// If worklets is ever legitimately installed again the plugin re-engages by itself.
function nativewindPreset() {
  const plugins = [
    require('react-native-css-interop/dist/babel-plugin').default,
    [
      require.resolve('@babel/plugin-transform-react-jsx'),
      { runtime: 'automatic', importSource: 'react-native-css-interop' },
    ],
  ];
  try {
    plugins.push(require.resolve('react-native-worklets/plugin'));
  } catch {
    // worklets absent (DL-44) — animated utilities are unused, nothing to transform
  }
  return { plugins };
}
