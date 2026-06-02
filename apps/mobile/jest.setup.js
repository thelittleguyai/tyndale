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
