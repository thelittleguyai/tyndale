import type { Config } from 'tailwindcss';

/**
 * Palette mirrors packages/shared/src/design-tokens.ts, which is the source of
 * truth. Tailwind configs can't import the TS tokens at config-eval time, so we
 * redeclare the values here (per the Phase 1B prompt's "redeclare to match" option).
 * Keep this in sync with @tyndale/shared/design-tokens.
 */
const config: Config = {
  content: ['./src/**/*.{ts,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#0F2A28', deep: '#0A1E1C', soft: '#152F2D' },
        navy: { DEFAULT: '#0E1F2B', deep: '#091621', soft: '#15242E' },
        cream: { DEFAULT: '#F5F1EA', soft: '#FAF7F2' },
        surface: '#FFFFFF',
        teal: { DEFAULT: '#1F4E4A', deep: '#173D3A', soft: '#E0EAE8', tint: '#F0F5F4' },
        sage: { DEFAULT: '#3DAA7E', deep: '#2E8862', soft: '#E5F2EB', tint: '#F2F8F4' },
        amber: { DEFAULT: '#E08A3C', deep: '#C26F26', soft: '#FBEBD8' },
        rose: { DEFAULT: '#C75252', soft: '#F7E0E0' },
        line: { DEFAULT: '#E4DFD5', soft: '#EFEAE0', card: '#ECE6D9', dark: '#1F3340' },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        md: '14px',
        lg: '20px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,42,40,0.04), 0 4px 12px rgba(15,42,40,0.05)',
        elev: '0 2px 4px rgba(15,42,40,0.05), 0 8px 24px rgba(15,42,40,0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
