// The mobile lint gate (08-27 audit carry-over, landed 2026-09-21): Expo's defaults (react,
// react-hooks, import, expo, typescript-eslint) + two React Native accessibility invariants.
//
// Why the invariants are `no-restricted-syntax` selectors and not a plugin: the RN a11y
// plugin (eslint-plugin-react-native-a11y 3.5.1, its latest) declares `peer eslint ^3–^8`.
// npm will not resolve it beside ESLint 9 without --legacy-peer-deps, and a repo-wide
// legacy-peer-deps changes how the whole Expo tree installs (see DL-44 for how that goes).
// Its rules are ESLint-9-compatible in practice — revisit when it publishes a v9 peer range.
//
// Zero-warning policy, same as the web apps: fix it, or disable the line WITH A REASON.
const comments = require('@eslint-community/eslint-plugin-eslint-comments/configs');
const expoConfig = require('eslint-config-expo/flat');
const { defineConfig } = require('eslint/config');

const A11Y_ATTR = '/^(accessibilityRole|role|accessible|aria-hidden|accessibilityElementsHidden|importantForAccessibility)$/';

module.exports = defineConfig([
  { ignores: ['dist/**', 'node_modules/**', '.expo/**', 'expo-env.d.ts', 'nativewind-env.d.ts'] },
  expoConfig,
  comments.recommended,
  {
    linterOptions: { reportUnusedDisableDirectives: 'error' },
    rules: {
      '@eslint-community/eslint-comments/require-description': ['error', { ignore: ['eslint-enable'] }],
    },
  },
  {
    // Expo registers the typescript-eslint plugin for TS files only — so must this override.
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
    },
  },
  {
    rules: {
      // In React Native, `'` and `"` inside <Text> are just characters — there is no HTML to
      // escape, and rewriting product copy into &apos; entities helps nobody. `>` and `}` stay
      // forbidden: in JSX text those are almost always a stray bracket from a bad edit.
      'react/no-unescaped-entities': ['error', { forbid: ['>', '}'] }],
    },
  },
  {
    files: ['jest.setup.js', '__tests__/**'],
    languageOptions: { globals: { jest: 'readonly' } },
    rules: {
      // jest.mock() factories are hoisted ABOVE every import, so a factory can only reach a
      // module with require(). That is the documented jest pattern, not a style lapse.
      '@typescript-eslint/no-require-imports': 'off',
      // …and for the same reason the suites declare their mocks FIRST and import the unit under
      // test after them: the file then reads in the order it actually executes.
      'import/first': 'off',
    },
  },
  {
    files: ['app/**/*.tsx', 'components/**/*.tsx'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          // A bare touchable has no role: a screen reader reads its label as plain text and never
          // says it can be activated. PressableScale defaults to `button`; raw ones must say.
          selector: `JSXOpeningElement[name.name=/^(Pressable|TouchableOpacity|TouchableHighlight|TouchableWithoutFeedback)$/]:not(:has(> JSXAttribute[name.name=${A11Y_ATTR}])):not(:has(> JSXSpreadAttribute))`,
          message:
            'A touchable needs accessibilityRole (or role) — or use PressableScale, which defaults to "button". Purely decorative? Say so with accessible={false}.',
        },
        {
          selector: `JSXOpeningElement[name.name='Image']:not(:has(> JSXAttribute[name.name=/^(accessibilityLabel|aria-label|alt|accessible|aria-hidden|accessibilityElementsHidden|importantForAccessibility)$/])):not(:has(> JSXSpreadAttribute))`,
          message:
            'An <Image> needs accessibilityLabel (or alt) — or, if decorative, accessible={false} so a screen reader skips it.',
        },
      ],
    },
  },
]);
