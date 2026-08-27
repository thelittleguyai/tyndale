/**
 * Tyndale design tokens — THE single source of truth for every surface.
 *
 * Consumers: apps/web-marketing (Next.js), apps/admin (re-exports this module),
 * apps/mobile (theme/tokens.ts re-shapes `semantic` into its slot API). No colour value may
 * be defined anywhere else — `runtime/tests/../test_no_raw_hex` (and the mobile jest guard)
 * fail the build if a raw hex appears in app source outside this file.
 *
 * The two Tailwind configs and apps/mobile/global.css MIRROR these values by hand (Tailwind
 * can't import TS at config-eval time). They are the one sanctioned duplication and are
 * checked against this file by the mirror-sync test — never edit a mirror alone.
 *
 * Palette authority: `docs/build-kit/36_design_conformance_checklist.md` §A (Brock). The five
 * §A hexes live in `brand` below; everything else derives from them.
 */

/**
 * Brock's checklist §A palette — the acceptance authority. Every other colour in this file is
 * derived from these five (or is a neutral/state colour §A doesn't specify).
 * All five verified ≥4.5:1 against our text colours — see docs/design/palette_reconciliation.md.
 */
export const brand = {
  teal: '#3E5C57', //  A1 primary brand teal
  navy: '#1D2A38', //  A2 nav / header
  money: '#2E7D5B', //  A4 money / savings figures (replaced sage #3DAA7E, which failed AA at 2.90:1)
  citation: '#2C6E8F', //  A6 citation / source chips — a rendering requirement for [B] strings
  cream: '#FAF7F0', //  A7 page background
} as const;

// Palette
export const colors = {
  // Dark theme (dashboard, signed-in app)
  ink: { DEFAULT: '#0F2A28', deep: '#0A1E1C', soft: '#152F2D' },
  navy: { DEFAULT: brand.navy, deep: '#17212C', soft: '#2A3946' },
  // Light theme (marketing)
  cream: { DEFAULT: brand.cream, soft: '#FDFBF8' },
  surface: '#FFFFFF',
  // Accents (shared across themes)
  teal: { DEFAULT: brand.teal, deep: '#304844', soft: '#E4E8E7', tint: '#F3F5F5' },
  // `sage` is the money/savings ramp (A4). Derived shades regenerated from the new base.
  sage: { DEFAULT: brand.money, deep: '#246247', soft: '#E2EDE8', tint: '#F2F7F5' },
  amber: { DEFAULT: '#E08A3C', deep: '#C26F26', soft: '#FBEBD8' },
  rose: { DEFAULT: '#C75252', soft: '#F7E0E0' },
  /**
   * Citation / source chips — checklist A6. A dedicated SEMANTIC slot, not an accent reuse:
   * `[B]` voice-tier strings may only render WITH their citation chip (orchestration script
   * §0 rule 3), so "the colour a citation is" is a rendering requirement, not decoration.
   * Contrast: 5.62:1 white-on-chip, 5.26:1 chip-on-cream — both AA at body size.
   */
  citation: { DEFAULT: brand.citation, soft: '#E1EBEF', deep: '#225670', tint: '#F2F6F8' },
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
  // Round-2 T6 — the prototype's names, extending (not replacing) ours: `soft` is the card
  // shadow, `float` sits one step above elev for overlays/menus. Same ink-tinted shadow family.
  soft: '0 1px 2px rgba(15, 42, 40, 0.04), 0 4px 12px rgba(15, 42, 40, 0.05)',
  float: '0 4px 8px rgba(15, 42, 40, 0.06), 0 12px 32px rgba(15, 42, 40, 0.10)',
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

/**
 * ── Member-app semantic palette — "Clear day" (light) / "Midnight ledger" (dark) ──────────
 *
 * ONE set of semantic slot names, two palettes: a component references a ROLE (`bg.surface`,
 * `text.primary`, `accent`) and the mode picks the value. Lives here rather than in
 * apps/mobile so there is exactly one place a colour is defined; apps/mobile/theme/tokens.ts
 * re-exports these unchanged, so component imports are untouched.
 *
 * Dark is NOT a mechanical inversion — a #3E5C57 accent on a #0C1210 page is ~1.9:1 and
 * unusable. Dark counterparts are the same hue lifted to legibility, each verified ≥4.5:1
 * against dark page AND surface (see the contrast table in the conformance sweep).
 */
export type SemanticColors = {
  bg: { page: string; surface: string; surfaceRaised: string; inset: string };
  text: { primary: string; secondary: string; faint: string };
  border: { hairline: string; strong: string };
  accent: string;
  accentTint: string;
  onAccent: string;
  /** Money / savings figures — checklist A4. Kept distinct from `accent` on purpose. */
  money: string;
  /** Citation / source chips — checklist A6. */
  citation: { base: string; tint: string; onTint: string };
  success: { base: string; tint: string; onTint: string };
  warning: { base: string; tint: string; onTint: string };
  danger: { base: string; tint: string; onTint: string };
  moment: { bg: string; border: string; emphasis: string; text: string; textFaint: string; inset: string };
};

/** Light — "Clear day" (default). Page background is Brock's A7 cream. */
export const light: SemanticColors = {
  bg: {
    page: brand.cream, //  A7
    surface: '#FFFFFF',
    surfaceRaised: '#FFFFFF', // elevation is carried by shadow, not a lighter fill
    inset: '#EFECE4', // derived: a recessed well, one step darker than page
  },
  // text.faint was #888780 (3.37:1 — below AA); darkened to the nearest same-hue AA value.
  text: { primary: '#1A2B27', secondary: '#5F5E5A', faint: '#726F69' },
  border: { hairline: '#DCD9D3', strong: '#C2BFB8' /* derived from cream */ },
  accent: brand.teal, //  A1
  accentTint: '#ECEFEE', // derived: teal at 10%
  onAccent: '#FFFFFF',
  money: brand.money, //  A4 — 5.00:1 white-on-green (was sage #3DAA7E at 2.90:1)
  citation: { base: brand.citation, tint: '#E1EBEF', onTint: '#225670' }, //  A6
  success: { base: brand.money, tint: '#E2EDE8', onTint: '#1C4E39' },
  // warning/danger bases were #BA7517 (3.48) and #D2544B (3.84) — both below AA as text.
  warning: { base: '#9A5F12', tint: '#FAEEDA', onTint: '#7A4D0F' },
  danger: { base: '#C1443B', tint: '#FBE4E1', onTint: '#8F2F28' },
  moment: {
    bg: '#12332E', // derived from brand teal, darkened — the card that pops on light pages
    border: '#2A4F49',
    emphasis: '#7FC9B4',
    text: '#E8F0EE',
    textFaint: '#A9CFC5',
    inset: 'rgba(255,255,255,0.07)', // the headline well on the always-dark card
  },
};

/** Dark — "Midnight ledger" (user-selectable). Same hues, lifted for legibility. */
export const dark: SemanticColors = {
  bg: {
    page: '#0C1210',
    surface: '#141D19',
    surfaceRaised: '#1C2B25',
    inset: '#0E1512',
  },
  // text.faint was #5C6E67 (3.50:1 on page) — lightened to the nearest same-hue AA value.
  text: { primary: '#F2F5F3', secondary: '#8FA39B', faint: '#748981' },
  border: { hairline: '#22312B', strong: '#2E4238' },
  accent: '#5DCAA5', // brand teal lifted for dark surfaces (9.42:1 on page)
  accentTint: '#123028',
  onAccent: '#04342C',
  money: '#4FBF8B', // brand money lifted for dark (8.25:1 on page)
  citation: { base: '#7FB6D3', tint: '#12303D', onTint: '#BFDDEB' }, // brand citation lifted
  success: { base: '#4FBF8B', tint: '#123026', onTint: '#A7E5C9' },
  warning: { base: '#FAC775', tint: '#3D2E12', onTint: '#FAC775' },
  danger: { base: '#E5776C', tint: '#3A1A16', onTint: '#F0A79F' },
  moment: {
    bg: '#0F3A2D',
    border: '#1D9E75',
    emphasis: '#5DCAA5',
    text: '#DFF5EC',
    textFaint: '#9FE1CB',
  
    inset: 'rgba(255,255,255,0.07)',
  },
};

export const semantic = { light, dark } as const;
export type ThemeMode = 'light' | 'dark' | 'system';

/**
 * Type scale — weights 400/500 only, ALL-CAPS killed app-wide (sentence-case captions).
 *
 * CONFORMANCE A8 ("body ≥16px everywhere, line-height 1.5"): body is 16/1.55 as of
 * 2026-08-17. Heading stays 16 too — it separates from body by WEIGHT (500 vs 400), which
 * held before at 16-vs-14 only by accident of size. The floor applies to body COPY; caption
 * and micro are label scales with their own sizes, not exceptions to A8.
 */
export const type = {
  display: { size: 28, weight: '500', lineHeight: 1.2 },
  title: { size: 21, weight: '500', lineHeight: 1.25 },
  heading: { size: 16, weight: '500', lineHeight: 1.4 },
  body: { size: 16, weight: '400', lineHeight: 1.55 },
  caption: { size: 12, weight: '400', lineHeight: 1.4 },
  micro: { size: 11, weight: '400', lineHeight: 1.3 },
} as const;

/** 4px base grid. Card padding 14–16; section gap 20–24. */
export const space = { grid: 4, cardPadding: 16, sectionGap: 24 } as const;

/** Controls 8 · cards 16 · moment cards 24 · chips 999. Round-2 T1: cards 12→16, moment 16→24
 * (the prototype's rounded-2xl/3xl scale), applied 2026-08-17 with Phil's go; controls stay 8. */
export const radius = { control: 8, card: 16, moment: 24, chip: 999 } as const;

/** Minimum interactive target — checklist A10. */
export const minTapTarget = 44;

export const tokens = {
  brand,
  colors,
  semantic,
  fonts,
  radii,
  radius,
  shadows,
  type,
  space,
  minTapTarget,
  logoSvg,
} as const;

export type TyndaleTokens = typeof tokens;

export default tokens;
