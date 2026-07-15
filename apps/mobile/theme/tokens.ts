/**
 * Tyndale member-app design tokens — the single source of truth for the "Clear day / Midnight
 * ledger" system (design review 2026-07-12). Two palettes, ONE set of semantic slot names, so a
 * component references a role (`bg.surface`, `text.primary`, `accent`) and the mode decides the
 * value. Light "Clear day" is the default; dark "Midnight ledger" is a user-selectable mode.
 *
 * These values are mirrored as CSS custom properties in `global.css` (`:root` = light, `.dark` =
 * dark) and referenced by name in `tailwind.config.js` — NativeWind/Tailwind configs can't import
 * TS at eval time, so this module stays the source of truth and the other two are kept in sync
 * (same discipline as packages/shared/src/design-tokens.ts). A few slots the spec left implicit
 * (light `surfaceRaised`/`inset`/`border.strong`, both `success`, dark `inset`/`accent.tint`,
 * moment text stops, dark `danger`) are derived here and marked.
 */

export type SemanticColors = {
  bg: { page: string; surface: string; surfaceRaised: string; inset: string };
  text: { primary: string; secondary: string; faint: string };
  border: { hairline: string; strong: string };
  accent: string;
  accentTint: string;
  onAccent: string;
  success: { base: string; tint: string; onTint: string };
  warning: { base: string; tint: string; onTint: string };
  danger: { base: string; tint: string; onTint: string };
  moment: { bg: string; border: string; emphasis: string; text: string; textFaint: string };
};

/** Light — "Clear day" (default). */
export const light: SemanticColors = {
  bg: {
    page: '#F7F8F5',
    surface: '#FFFFFF',
    surfaceRaised: '#FFFFFF', // derived: white; elevation is carried by shadow, not a lighter fill
    inset: '#ECEEE8', // derived: a recessed well, one step darker than page
  },
  text: { primary: '#1A2B27', secondary: '#5F5E5A', faint: '#888780' },
  border: { hairline: '#E3E5E0', strong: '#C9CCC5' /* derived: darker than hairline */ },
  accent: '#0F6E56', // deep teal
  accentTint: '#E1F5EE',
  onAccent: '#FFFFFF',
  success: { base: '#2E9E6B', tint: '#E4F4EC', onTint: '#12523A' }, // derived: green distinct from accent
  warning: { base: '#BA7517', tint: '#FAEEDA', onTint: '#7A4D0F' },
  danger: { base: '#D2544B', tint: '#FBE4E1', onTint: '#8F2F28' }, // coral family
  moment: {
    bg: '#04342C', // deep-ink green card that pops on light pages
    border: '#16564A', // derived: subtle lighter hairline on the dark card
    emphasis: '#5DCAA5',
    text: '#E1F5EE',
    textFaint: '#9FE1CB',
  },
};

/** Dark — "Midnight ledger" (user-selectable). */
export const dark: SemanticColors = {
  bg: {
    page: '#0C1210',
    surface: '#141D19',
    surfaceRaised: '#1C2B25',
    inset: '#0E1512', // derived: a recessed well, darker than surface
  },
  text: { primary: '#F2F5F3', secondary: '#8FA39B', faint: '#5C6E67' },
  border: { hairline: '#22312B', strong: '#2E4238' /* derived */ },
  accent: '#5DCAA5', // mint
  accentTint: '#123028', // derived: dark mint chip/selected bg
  onAccent: '#04342C',
  success: { base: '#4FBF8B', tint: '#123026', onTint: '#A7E5C9' }, // derived
  warning: { base: '#FAC775', tint: '#3D2E12', onTint: '#FAC775' },
  danger: { base: '#E5776C', tint: '#3A1A16', onTint: '#F0A79F' }, // derived: coral for dark
  moment: {
    bg: '#0F3A2D',
    border: '#1D9E75',
    emphasis: '#5DCAA5',
    text: '#DFF5EC', // derived
    textFaint: '#9FE1CB', // derived
  },
};

/** Type scale — weights 400/500 only, ALL-CAPS killed app-wide (sentence-case captions). */
export const type = {
  display: { size: 28, weight: '500', lineHeight: 1.2 },
  title: { size: 21, weight: '500', lineHeight: 1.25 },
  heading: { size: 16, weight: '500', lineHeight: 1.4 },
  body: { size: 14, weight: '400', lineHeight: 1.55 },
  caption: { size: 12, weight: '400', lineHeight: 1.4 },
  micro: { size: 11, weight: '400', lineHeight: 1.3 },
} as const;

/** 4px base grid. Card padding 14–16; section gap 20–24 (Tailwind's 4px scale covers these). */
export const space = { grid: 4, cardPadding: 16, sectionGap: 24 } as const;

/** Controls 8 · cards 12 · moment cards 16 · chips 999. */
export const radius = { control: 8, card: 12, moment: 16, chip: 999 } as const;

export const palettes = { light, dark } as const;
export type ThemeMode = 'light' | 'dark' | 'system';

export default palettes;
