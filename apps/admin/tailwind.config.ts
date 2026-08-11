import type { Config } from 'tailwindcss';

// Mirrors apps/web-marketing/tailwind.config.ts (the Tyndale design tokens).
const config: Config = {
  content: ['./src/**/*.{ts,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#0F2A28', deep: '#0A1E1C', soft: '#152F2D' },
        navy: { DEFAULT: '#1D2A38', deep: '#17212C', soft: '#2A3946' },
        cream: { DEFAULT: '#FAF7F0', soft: '#FDFBF8' },
        surface: '#FFFFFF',
        teal: { DEFAULT: '#3E5C57', deep: '#304844', soft: '#E4E8E7', tint: '#F3F5F5' },
        sage: { DEFAULT: '#2E7D5B', deep: '#246247', soft: '#E2EDE8', tint: '#F2F7F5' },
        amber: { DEFAULT: '#E08A3C', deep: '#C26F26', soft: '#FBEBD8' },
        rose: { DEFAULT: '#C75252', soft: '#F7E0E0' },
        citation: { DEFAULT: '#2C6E8F', soft: '#E1EBEF', deep: '#225670', tint: '#F2F6F8' },
        line: { DEFAULT: '#E4DFD5', soft: '#EFEAE0', card: '#ECE6D9', dark: '#1F3340' },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: { sm: '8px', md: '14px', lg: '20px' },
      boxShadow: {
        card: '0 1px 2px rgba(15,42,40,0.04), 0 4px 12px rgba(15,42,40,0.05)',
        elev: '0 2px 4px rgba(15,42,40,0.05), 0 8px 24px rgba(15,42,40,0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
