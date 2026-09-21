import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

// Pure-logic and render-to-string tests only (node environment, no DOM): the JSX transform Next
// applies at build time, and the `@/` alias from tsconfig, are all a component test needs.
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: { environment: 'node', include: ['src/**/*.test.{ts,tsx}'] },
});
