# Palette reconciliation — checklist §A vs. shipped tokens

**Status:** for Brock's call. Nothing in `packages/shared/src/design-tokens.ts` was overwritten,
with ONE exception noted below (`citation`, which the `[B]` renderer now requires).
**Date:** 2026-08-11 · **Sources:** `docs/build-kit/36_design_conformance_checklist.md` §A ·
`packages/shared/src/design-tokens.ts`

## First, a correction to the brief

The session brief's "we shipped" column did not match the repo. These are the **actual**
shipped values, read from the tokens file:

| Checklist | Brock's expected | Brief said we shipped | **Actually shipped** |
|---|---|---|---|
| A1 brand teal | `#3E5C57` | `#0F6E56` | **`#1F4E4A`** (`teal.DEFAULT`) |
| A2 nav/header navy | `#1D2A38` | "different family" | **`#0E1F2B`** (`navy.DEFAULT`) |
| A4 money/savings green | `#2E7D5B` | "accent reused" | **`#3DAA7E`** (`sage.DEFAULT`) |
| A6 citation/source blue | `#2C6E8F` | none | **none** — confirmed |
| A7 page background cream | `#FAF7F0` | `#F7F8F5` | **`#F5F1EA`** (`cream.DEFAULT`) |

So every row is a real difference, but four of the five are *closer* than the brief implied.

## The comparison, with contrast

Ratios computed against our text colours: ink `#0F2A28` and white `#FFFFFF`.

| # | Slot | Shipped | Brock's | Where it's used | Brock's value at AA |
|---|---|---|---|---|---|
| A1 | brand teal | `#1F4E4A` | `#3E5C57` | primary buttons, logo mark, links, focus rings | **PASS** — 7.31:1 white-on-teal, 6.83:1 on cream |
| A2 | nav/header navy | `#0E1F2B` | `#1D2A38` | dark surfaces, case-page status banner | **PASS** — 14.58:1 white-on-navy |
| A4 | money/savings | `#3DAA7E` | `#2E7D5B` | three-number hero, recovered tallies, finding amounts | **PASS** — 5.00:1 white-on-green |
| A6 | citation chip | *(none)* | `#2C6E8F` | **new semantic slot** — `[B]` source chips | **PASS** — 5.62:1 white-on-chip, 5.26:1 on cream |
| A7 | page background | `#F5F1EA` | `#FAF7F0` | app + marketing page background | background, not text — ink on it is **14.20:1 PASS** |

**Nothing in Brock's palette fails WCAG AA.** There is no contrast regression to flag back to
him — which was the thing this exercise was meant to catch.

## The finding that matters: adopting A4 FIXES a live AA failure

Our shipped money colour `sage #3DAA7E` is the weakest thing in the palette:

- white on `#3DAA7E` → **2.90:1** — fails AA (needs 4.5:1), fails even AA-large (3.0:1)
- `#3DAA7E` on cream → **2.57:1** — fails

Those are the *three-number hero* and *recovered* figures — the most important numbers in the
product, currently rendered below AA. Brock's `#2E7D5B` takes white-on-green to **5.00:1**.

**A4 is not a preference change; it is a bug fix.** Recommend adopting it regardless of what
happens to the rest of the palette.

## Recommendation

**Adopt Brock's five hexes as canonical** — his checklist is the acceptance authority, all
five clear AA, and A4 repairs a real failure. Two notes for him:

1. **A4 is the urgent one** (accessibility, not aesthetics). If he wants to keep a brighter
   green for anything decorative, the money/savings *figures* still need ≥4.5:1.
2. **A1 `#3E5C57` is lower-contrast than what we ship** (7.31 vs 9.35 white-on-teal). Still
   comfortably AA, so it's his call — flagging only so the change is deliberate.

The `soft`/`deep`/`tint` companion shades of each ramp were not specified in §A. If the base
hexes are adopted, those need regenerating from the new bases; they are currently derived from
the shipped ones.

## Implemented now (the one exception)

`colors.citation = { DEFAULT: '#2C6E8F', soft: '#E4EEF4', deep: '#22566F' }`

Added ahead of his answer because it is **not a palette preference but a rendering
dependency**: orchestration-script §0 rule 3 makes `[B]` legal/coverage strings render only
with a citation chip, so the chip needs a semantic colour to exist at all. `soft`/`deep` are
derived tints for chip fill and hover.

## Not implemented, pending his call

A1, A2, A4, A7 — the four base hexes. Applying them means updating `design-tokens.ts` **and**
the two Tailwind configs that redeclare the palette (`apps/mobile`, `apps/web-marketing`),
plus regenerating the companion shades. One commit once he answers.
