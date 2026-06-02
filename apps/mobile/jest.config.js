module.exports = {
  // Single-platform preset (not the default multi-project one) — faster, and it
  // keeps jest-expo's own transformIgnorePatterns (which correctly transform the
  // expo-modules-core / expo-* sources). We deliberately do NOT override
  // transformIgnorePatterns here — doing so previously broke that transform.
  preset: 'jest-expo/ios',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testMatch: ['<rootDir>/__tests__/**/*.test.{ts,tsx}'],
  moduleNameMapper: {
    '^@tyndale/shared$': '<rootDir>/../../packages/shared/src/index.ts',
    // Force a SINGLE React instance (the root-hoisted 19.2.6 that react-test-
    // renderer uses) so hooks don't hit "more than one copy of React". The app's
    // own react pin is untouched; this only affects the jest module graph.
    '^react$': '<rootDir>/../../node_modules/react',
    '^react-dom$': '<rootDir>/../../node_modules/react-dom',
  },
};
