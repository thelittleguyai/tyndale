import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import comments from '@eslint-community/eslint-plugin-eslint-comments/configs';
import { FlatCompat } from '@eslint/eslintrc';

// The frontend lint gate (08-27 audit carry-over, landed 2026-09-21). Next's defaults
// (core-web-vitals = react + react-hooks + @next/next, plus the typescript preset) and the
// full jsx-a11y recommended set — Next only enables six of its rules.
//
// Zero-warning policy: `npm run lint` passes --max-warnings 0, so a "warning" is a failure
// with a softer name. Anything the gate flags is FIXED, or disabled on its line WITH A REASON
// (`-- why`), which eslint-comments/require-description enforces. No file- or rule-wide
// suppressions to make a number go down.
const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

const config = [
  { ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts'] },
  ...compat.extends('next/core-web-vitals', 'next/typescript', 'plugin:jsx-a11y/recommended'),
  comments.recommended,
  {
    linterOptions: { reportUnusedDisableDirectives: 'error' },
    rules: {
      '@eslint-community/eslint-comments/require-description': ['error', { ignore: ['eslint-enable'] }],
      // `_unused` is the repo's spelling for "deliberately unused" (tsc's noUnused* agrees).
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
    },
  },
];

export default config;
