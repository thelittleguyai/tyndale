# Tyndale member-app redesign — design direction record

**Date:** 2026-07-12 · **Decided by:** Phil (mockup review) · **Status:** APPROVED — both directions, full pass
**Mockups:** `redesign_direction_a_clear_day.html` (light, DEFAULT) · `redesign_direction_b_midnight_ledger.html` (dark, user-selectable)
**Build prompt:** `claude_code_redesign_prompt.md` (Phil's outputs folder) — token system + full member-app screen pass.

## Why (the critique, condensed)

Page-by-page review of dev (2026-07-12) against consumer health-fintech standards (Cedar, Oscar, Copilot Money, Stripe-class):

- **Three clashing surface systems on one screen** — white cards + dark cards + tinted banners on the dashboard; no unified elevation model.
- **No type scale** — headings are bold body text; ALL-CAPS low-contrast micro-labels fail WCAG AA in places.
- **One muted green doing every job** (brand, success, CTA, link) — no semantic status colors.
- **Moments aren't moments** — the three-number reveal (Brock D0: a designed moment) rendered as an ordinary bubble.
- **Text-density ~3× norm** on verification cards; three equal-weight gray buttons, no primary/secondary hierarchy.
- Best-structured page (sub-case) still renders its soul (the three numbers) at the same visual weight as metadata. Also surfaced a bug: raw enum `no_immediate_action_required` leaking into user copy (fixed in the redesign pass).

## The decision

One semantic token system, two palettes:

| Slot | A — Clear day (light, default) | B — Midnight ledger (dark) |
|---|---|---|
| Page | `#F7F8F5` | `#0C1210` |
| Surface / raised | `#FFFFFF` | `#141D19` / `#1C2B25` |
| Hairline | `#E3E5E0` | `#22312B` |
| Text primary / secondary / faint | `#1A2B27` / `#5F5E5A` / `#888780` | `#F2F5F3` / `#8FA39B` / `#5C6E67` |
| Accent (+tint) | `#0F6E56` (`#E1F5EE`) | `#5DCAA5` (on-accent `#04342C`) |
| Warning (+tint) | `#BA7517` (`#FAEEDA`) | `#FAC775` (`#3D2E12`) |
| Moment card | bg `#04342C`, text `#9FE1CB`/`#E1F5EE`, emphasis `#5DCAA5` | bg `#0F3A2D`, border `#1D9E75`, emphasis `#5DCAA5` |

**Type scale:** 28/21/16/14/12/11 · weights 400 + 500 only · sentence case everywhere (ALL-CAPS retired).
**Spacing:** 4px grid · card padding 14–16 · section gap 20–24. **Radii:** 8 controls / 12 cards / 16 moment cards / 999 chips.
**Contrast:** every pair ≥ WCAG AA 4.5:1. **Touch targets:** ≥ 44px.

## Component kit
`Card` (the only card primitive) · `MetricCard` · `StatusChip` · `Button` (primary/secondary/tertiary) · `MomentCard` (reserved for exactly: three-number reveal, first-case unlock, the two continuous-journey beats — Brock D0) · `SectionHeader` · `ListRow` · `Disclosure` (long explainers collapsed by default).

## Notes
- Copy in the mockups is design-placeholder; real strings come from Brock's D1 orchestration-script registry (the reveal verdict line needs a clean-bill variant — flagged to Brock 2026-07-10).
- Admin console and marketing site are separate, later passes.
- Redesign is presentation-only: no behavior/routing/API changes; e2e thread assertions unaffected.
