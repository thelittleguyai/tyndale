/**
 * Tyndale design tokens — the canonical source of truth for both frontends.
 *
 * apps/web-marketing (Next.js) and apps/mobile (Expo) both consume these.
 * Tailwind configs in each app redeclare the palette to match these values
 * (Tailwind/NativeWind configs can't easily import TS at config-eval time);
 * this module remains the source of truth — keep the two in sync.
 */

// Palette
export const colors = {
  // Dark theme (dashboard, signed-in app)
  ink: { DEFAULT: '#0F2A28', deep: '#0A1E1C', soft: '#152F2D' },
  navy: { DEFAULT: '#0E1F2B', deep: '#091621', soft: '#15242E' },
  // Light theme (marketing)
  cream: { DEFAULT: '#F5F1EA', soft: '#FAF7F2' },
  surface: '#FFFFFF',
  // Accents (shared across themes)
  teal: { DEFAULT: '#1F4E4A', deep: '#173D3A', soft: '#E0EAE8', tint: '#F0F5F4' },
  sage: { DEFAULT: '#3DAA7E', deep: '#2E8862', soft: '#E5F2EB', tint: '#F2F8F4' },
  amber: { DEFAULT: '#E08A3C', deep: '#C26F26', soft: '#FBEBD8' },
  rose: { DEFAULT: '#C75252', soft: '#F7E0E0' },
  // Borders + neutrals
  border: { DEFAULT: '#E4DFD5', soft: '#EFEAE0', card: '#ECE6D9', dark: '#1F3340' },
  // Text on dark backgrounds
  inkOnDark: {
    DEFAULT: '#FFFFFF',
    muted: 'rgba(255,255,255,0.78)',
    faint: 'rgba(255,255,255,0.55)',
  },
} as const;

export const fonts = {
  sans: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
  mono: 'JetBrains Mono, ui-monospace, monospace',
} as const;

export const radii = { sm: 8, md: 14, lg: 20 } as const;

export const shadows = {
  card: '0 1px 2px rgba(15, 42, 40, 0.04), 0 4px 12px rgba(15, 42, 40, 0.05)',
  elev: '0 2px 4px rgba(15, 42, 40, 0.05), 0 8px 24px rgba(15, 42, 40, 0.08)',
} as const;

/**
 * Tyndale logo mark, as an inline SVG string.
 * Extracted verbatim from docs/tyndale-spec/01_overview.html (`.header-logo-mark`),
 * with the stylesheet class removed so consumers can size/style it freely.
 * Render on web via dangerouslySetInnerHTML; on native, feed to react-native-svg
 * (SvgXml) once that dependency lands.
 */
export const logoSvg =
  '<svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Tyndale">' +
  '<circle cx="40" cy="40" r="38" fill="none" stroke="#1F4E4A" stroke-width="3"/>' +
  '<rect x="26" y="20" width="28" height="36" rx="3" fill="#1F4E4A"/>' +
  '<line x1="32" y1="30" x2="48" y2="30" stroke="#F5F1EA" stroke-width="2.5" stroke-linecap="round"/>' +
  '<line x1="32" y1="36" x2="48" y2="36" stroke="#F5F1EA" stroke-width="2.5" stroke-linecap="round"/>' +
  '<line x1="32" y1="42" x2="42" y2="42" stroke="#F5F1EA" stroke-width="2.5" stroke-linecap="round"/>' +
  '<path d="M34 50 L38 54 L48 44" stroke="#3DAA7E" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' +
  '</svg>';

export const tokens = { colors, fonts, radii, shadows, logoSvg } as const;

export type TyndaleTokens = typeof tokens;

export default tokens;
