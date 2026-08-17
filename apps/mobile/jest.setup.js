/* Jest setup (Phase CO-10): light mocks so chat components render in isolation. */

// Render lucide icons as plain Views — avoids react-native-svg in tests.
jest.mock('lucide-react-native', () => {
  const React = require('react');
  const { View } = require('react-native');
  return new Proxy(
    {},
    { get: () => (props) => React.createElement(View, props) },
  );
});

// Default expo-router mock; tests that assert navigation override this per-file.
jest.mock('expo-router', () => {
  const React = require('react');
  return {
    useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
    useLocalSearchParams: () => ({}),
    Link: ({ children }) => React.createElement(React.Fragment, null, children),
  };
});

// NativeWind's colorScheme runtime isn't initialized under jest, so calling setColorScheme throws.
// Stub the hook (the ONLY runtime import of 'nativewind' is theme/useTheme). className styling is
// compiled by the babel transform, not this hook, so component rendering is unaffected.
jest.mock('nativewind', () => ({
  useColorScheme: () => ({
    colorScheme: 'light',
    setColorScheme: jest.fn(),
    toggleColorScheme: jest.fn(),
  }),
}));


// expo-camera (native capture, 2026-08-17): render CameraView as a plain View; permission
// defaults to GRANTED so component tests exercise the live state. Tests override per-case.
jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    CameraView: React.forwardRef((props, ref) => React.createElement(View, { ...props, ref })),
    useCameraPermissions: jest.fn(() => [
      { granted: true, canAskAgain: true },
      jest.fn(),
    ]),
  };
});
