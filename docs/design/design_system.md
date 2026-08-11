# Tyndale Design System — as shipped

**For:** Brock (design review) · **From:** Phil · **Date:** 2026-07-15 · **Status:** LIVE in dev (member app)
**Companions:** `redesign_direction_a_clear_day.html`, `redesign_direction_b_midnight_ledger.html` (approved mockups), `README.md` (decision record). This document describes what is actually running.

---

## 1. What this is

The visual and interaction system for the member app (`apps/mobile`), shipped 2026-07-14/15 after the mockup review. It replaced an unsystematized UI (three clashing surface treatments, no type scale, one green doing every job) with a token-driven system in two modes. Admin console and marketing site are explicitly out of scope — later passes.

## 2. Design principles

The system encodes the product's doctrine visually. Each principle below traces to a locked decision.

1. **Honesty has a visual grammar.** Confirmed and estimated dollars never share a style — confirmed renders in accent, estimated in neutral with an explicit "estimated" qualifier (your §3 counts-before-ratios rule, applied to pixels). Progress bars fill only on real stage completion — no fabricated percentages (D2). Unreadable documents, incomplete audits, and missing inputs get their own honest states, never disguised success.
2. **Moments are scarce by construction.** Exactly four surfaces may use the `MomentCard` treatment: the three-number reveal, the first-case unlock, and the two continuous-journey beats (D0 + your binding principle #2). Everything else is ordinary surface. Scarcity is enforced in the component, not by convention — a fifth use is a code review flag.
3. **Calm by default, weight where money is.** One accent color; semantic amber/coral reserved for status; the biggest type on any screen is a dollar figure the user should care about. The reveal's third number is the largest text in the product (30/500).
4. **Text earns its place.** Long explainers (the "typically you'd have" content) live behind progressive disclosure, collapsed by default. Verification cards lead with code · plain name · dollars, one body sentence, then an expandable. This cut on-screen text density roughly 3× on the densest cards.
5. **The words are yours.** No system-authored copy is engineering-owned: thread orchestration renders D1 registry keys verbatim; the dashboard's generated summary passes a banned-pattern validator (no invented humans, teams, or process) with a deterministic D1-keyed fallback. Staging refuses to boot with placeholder copy active.

## 3. Color — one semantic vocabulary, two palettes

Semantic slots are the API; palettes fill them. Light "Clear day" is the intended default; dark "Midnight ledger" is user-selectable (Settings → Appearance: Light / Dark / System, persisted).

| Slot | Clear day (light) | Midnight ledger (dark) | Used for |
|---|---|---|---|
| `bg.page` | `#F7F8F5` | `#0C1210` | Screen canvas |
| `bg.surface` | `#FFFFFF` | `#141D19` | Cards (the only card fill) |
| `bg.surfaceRaised` | — | `#1C2B25` | Dark-mode elevation step |
| `bg.inset` | `#EDEEEA` | `#22312B` | Wells, progress tracks |
| `border.hairline` | `#E3E5E0` | `#22312B` | All card borders |
| `text.primary` | `#1A2B27` | `#F2F5F3` | Headings, values |
| `text.secondary` | `#5F5E5A` | `#8FA39B` | Supporting copy |
| `text.faint` | `#888780` | `#5C6E67` | Captions, qualifiers |
| `accent` / on-accent | `#0F6E56` / white | `#5DCAA5` / `#04342C` | Primary actions, confirmed dollars |
| `accent.tint` | `#E1F5EE` | `#0F3A2D` | Chips, selected states, D4b suggestions |
| `warning` / tint | `#BA7517` / `#FAEEDA` | `#FAC775` / `#3D2E12` | Needs-documents, deadlines |
| `danger` family | coral ramp | coral ramp | Destructive, overdue |
| `moment.bg` | `#04342C` | `#0F3A2D` (+ `#1D9E75` border) | MomentCard only |
| `moment.emphasis` | `#5DCAA5` | `#5DCAA5` | The third number |

The moment card is deliberately the inversion point: in light mode it is the one dark object on the page (maximum pop for the reveal); in dark mode it is the one *green-cast* surface. Either way it cannot be mistaken for an ordinary card.

## 4. Typography, spacing, shape

- **Type scale:** 28 display · 21 title · 16 heading · 14 body (1.55 line height) · 12 caption · 11 micro. **Two weights: 400, 500.** No ALL-CAPS anywhere — retired app-wide in favor of sentence-case captions.
- **Spacing:** 4px base grid; 14–16 card padding; 20–24 section gaps.
- **Radii:** 8 controls · 12 cards · 16 moment cards · 999 chips.
- **Contrast:** every text/background pair ≥ WCAG AA 4.5:1 (audited per palette). **Touch targets ≥ 44px.**

## 5. Component kit (the only building blocks)

| Component | Anatomy | Rules |
|---|---|---|
| `Card` | surface + hairline + 12r | The sole card primitive; ad-hoc grays are gone |
| `MetricCard` | caption label / 22px value / micro qualifier / optional 4px track | Qualifier is mandatory when the number is estimated |
| `StatusChip` | tinted pill, 12px | success / warning / danger / neutral only — chips never invent new colors |
| `Button` | primary (accent fill) / secondary (hairline outline) / tertiary (text) | One primary per view; verification uses primary Yes / secondary No / tertiary Not sure |
| `MomentCard` | moment slots, 16r, full-width | The four sanctioned moments only (see §2.2) |
| `ListRow` | title / second line / trailing chip (+ ✕ where removable) | Record rows: provider + date-of-service title (typed fields), state-specific second line, chip = case state; title may never be a status string (tested) |
| `Disclosure` | one-line link → expandable body | Default collapsed; hosts all long explainers |
| `SectionHeader` | 13/500 sentence case | Replaces ALL-CAPS labels |

## 6. Screen anatomy (as live)

- **Record (dashboard):** greeting (display) → generated one-to-two-sentence status summary (validated + cached, §2.5) → four MetricCards (recovered · identified · deductible · OOP) → Quick Actions + chat banner → "Your record" ListRows. Removable test/dead cases carry ✕.
- **Thread (chat-first):** ONE live status card updating in place — four labeled 4px bars, sequential real fill (D2) — plus discrete messages only for asks, results, terminal states. Verification cards grouped ≤3 per message (D3); D4b suggestions render accent-tint + dashed border + "Suggested — tap to confirm". The reveal is a MomentCard; findings follow as Cards with citations, tier styling, feedback thumbs.
- **Sub-case summary:** status banner + deadline line → the same three-number MomentCard (its permanent home) → recovered/identified MetricCards → gameplan as numbered expandable rows, biggest dollars first → "Walk me through the calls" (call mode: pinned claim/dollar strip, steppable script sections, outcome capture) → findings.
- **Upload:** unchanged flow, warmed presentation; file rows as ListRows; honest per-document failure states.
- **Settings:** sectioned Cards; appearance control; consent toggle; legal links; account actions.

## 7. Motion and status

Minimal by policy: progress bars fill, chips change tint, suggested-state pulses are static styling (no animation library added). The "taking longer than expected" state and honest-partial terminals are styled as calm information, not alarm.

## 8. Known gaps / your call (design-review asks)

1. **Default mode.** Spec says light default; the app currently honors system preference on first run. Confirm intent: force light for first-run (my reading of the mockup decision) or keep system-follow?
2. **State-aware dashboard ordering.** Quick Actions now sit above the Record (Phil's call, 2026-07-15). Once real users have live cases, consider flipping order contextually (results-ready users care about the Record first). Your continuous-journey principle would support it — flagging as a future decision, not built.
3. **Chip taxonomy.** Current states: Results ready / Verify visit / Needs documents / Couldn't read / In progress. Worth your naming pass alongside the D1 script — these are voice surfaces too.
4. **Empty states.** First-run Record (zero cases) uses a plain invitation; no illustration system exists yet. Cheap to add later; decide if it matters for launch.
5. **The reveal verdict line and completion line need their variants** (clean-bill, zero-findings) in the D1 drop — the design reserves the space; the words are yours.

## 9. Out of scope, deliberately

Admin console (functional, unstyled by this system) · marketing site · email templates (nudges render from D1-adjacent templates but haven't had a design pass) · print/PDF outputs · the unlock MomentCard's payment flow (built to your mock, dark behind flags pending the pricing rework).
