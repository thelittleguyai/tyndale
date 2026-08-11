/**
 * Tyndale member-app design tokens — "Clear day / Midnight ledger" (design review 2026-07-12).
 *
 * THIS FILE DEFINES NO VALUES. Every colour, size and radius is re-exported from
 * `@tyndale/shared` (packages/shared/src/design-tokens.ts), which is the single source of
 * truth for the app, the admin console and the marketing site alike — that duplication is
 * what let the app and the landing page drift apart, and it's now closed.
 *
 * The semantic slot API is UNCHANGED (`bg.page`, `text.primary`, `accent`, `moment.*`, …), so
 * no component needs to change: a component references a ROLE and the mode decides the value.
 *
 * These values are mirrored as CSS custom properties in `global.css` (`:root` = light, `.dark`
 * = dark) and referenced by name in `tailwind.config.js` — NativeWind/Tailwind can't import TS
 * at config-eval time. Those mirrors are checked against the shared file by the mirror-sync
 * test; never edit one on its own.
 */

export type { SemanticColors, ThemeMode } from '@tyndale/shared';
export {
  brand,
  dark,
  light,
  minTapTarget,
  radius,
  semantic as palettes,
  space,
  type,
} from '@tyndale/shared';

import { semantic } from '@tyndale/shared';

export default semantic;
