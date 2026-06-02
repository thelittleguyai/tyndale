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
      ...(isTest ? [] : ['nativewind/babel']),
    ],
  };
};
