/** @type {import('tailwindcss').Config} */
// Palette mirrors packages/shared/src/design-tokens.ts (the source of truth).
// Keep in sync with @tyndale/shared/design-tokens and apps/web-marketing's config.
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  // Manual mode override (Settings toggle) drives a `.dark` class via NativeWind's colorScheme,
  // so semantic tokens swap without per-element dark: variants. Default is light ("Clear day").
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── "Clear day / Midnight ledger" SEMANTIC slots (theme/tokens.ts + global.css vars).
        // Reference a role, not a value; the active mode picks the value. Prefer these on all new
        // and redesigned surfaces — the literal palette below is legacy, kept only until every
        // screen is converted off it.
        page: 'var(--c-bg-page)',
        surface: { DEFAULT: 'var(--c-bg-surface)', raised: 'var(--c-bg-surface-raised)' },
        inset: 'var(--c-bg-inset)',
        primary: 'var(--c-text-primary)', // text-primary
        secondary: 'var(--c-text-secondary)', // text-secondary
        faint: 'var(--c-text-faint)', // text-faint
        hairline: 'var(--c-border-hairline)', // border-hairline
        strong: 'var(--c-border-strong)', // border-strong
        accent: { DEFAULT: 'var(--c-accent)', tint: 'var(--c-accent-tint)' },
        'on-accent': 'var(--c-on-accent)',
        // Money / savings figures — checklist A4. Kept distinct from `accent` on purpose:
        // a dollar the user recovers should not read as "a button".
        money: 'var(--c-money)',
        // Citation / source chips — checklist A6. A rendering requirement, not decoration:
        // `[B]` strings and grounded findings render WITH their source in this colour.
        citation: {
          DEFAULT: 'var(--c-citation)',
          tint: 'var(--c-citation-tint)',
          'on-tint': 'var(--c-citation-on-tint)',
        },
        success: {
          DEFAULT: 'var(--c-success)', tint: 'var(--c-success-tint)', 'on-tint': 'var(--c-success-on-tint)',
        },
        warning: {
          DEFAULT: 'var(--c-warning)', tint: 'var(--c-warning-tint)', 'on-tint': 'var(--c-warning-on-tint)',
        },
        danger: {
          DEFAULT: 'var(--c-danger)', tint: 'var(--c-danger-tint)', 'on-tint': 'var(--c-danger-on-tint)',
        },
        moment: {
          bg: 'var(--c-moment-bg)', border: 'var(--c-moment-border)', emphasis: 'var(--c-moment-emphasis)',
          text: 'var(--c-moment-text)', 'text-faint': 'var(--c-moment-text-faint)',
        },
        // ── Legacy palette (pre-redesign; removed screen-by-screen as the pass converts them).
        ink: { DEFAULT: '#0F2A28', deep: '#0A1E1C', soft: '#152F2D' },
        navy: { DEFAULT: '#0E1F2B', deep: '#091621', soft: '#15242E' },
        cream: { DEFAULT: '#F5F1EA', soft: '#FAF7F2' },
        teal: { DEFAULT: '#1F4E4A', deep: '#173D3A', soft: '#E0EAE8', tint: '#F0F5F4' },
        sage: { DEFAULT: '#3DAA7E', deep: '#2E8862', soft: '#E5F2EB', tint: '#F2F8F4' },
        amber: { DEFAULT: '#E08A3C', deep: '#C26F26', soft: '#FBEBD8' },
        rose: { DEFAULT: '#C75252', soft: '#F7E0E0' },
        line: { DEFAULT: '#E4DFD5', soft: '#EFEAE0', card: '#ECE6D9', dark: '#1F3340' },
      },
      // Type scale — weights 400/500 only (theme/tokens.ts). Classes: text-display … text-micro.
      fontSize: {
        display: ['28px', { lineHeight: '34px', fontWeight: '500' }],
        title: ['21px', { lineHeight: '26px', fontWeight: '500' }],
        heading: ['16px', { lineHeight: '22px', fontWeight: '500' }],
        body: ['16px', { lineHeight: '25px', fontWeight: '400' }],
        caption: ['12px', { lineHeight: '17px', fontWeight: '400' }],
        micro: ['11px', { lineHeight: '14px', fontWeight: '400' }],
      },
      fontFamily: {
        // First entry is the expo-font-registered family (works on native and
        // is registered as an @font-face on web); 'Inter' is the Google Fonts
        // import in global.css so CSS weight mapping works properly on web.
        sans: ['Inter_400Regular', 'Inter', 'system-ui', 'sans-serif'],
      },
      // Token radii from @tyndale/shared design-tokens (radii = {sm:8, md:14, lg:20}).
      // Namespaced so Tailwind's default rounded-sm/md/lg scale (used throughout
      // the existing screens) keeps rendering unchanged.
      borderRadius: {
        'token-sm': '8px',
        'token-md': '14px',
        'token-lg': '20px',
        // Redesign radii (theme/tokens.ts): controls 8 · cards 12 · moment cards 16 · chips 999.
        control: '8px',
        card: '12px',
        moment: '16px',
        chip: '999px', // the comment above always claimed this; it was never actually defined
      },
      // Token shadows from @tyndale/shared design-tokens (shadows.card / shadows.elev).
      boxShadow: {
        card: '0 1px 2px rgba(15, 42, 40, 0.04), 0 4px 12px rgba(15, 42, 40, 0.05)',
        elev: '0 2px 4px rgba(15, 42, 40, 0.05), 0 8px 24px rgba(15, 42, 40, 0.08)',
      },
    },
  },
  plugins: [],
};
