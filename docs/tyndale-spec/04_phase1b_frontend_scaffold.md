# Phase 1B — Frontend Scaffold · Claude Code Prompt

**For:** Phil (frontend track) — paste into a fresh Claude Code session at `~/code/tyndale`
**Goal:** Scaffold the universal Expo app (`apps/mobile`), the Next.js marketing landing (`apps/web-marketing`), the Tyndale design system, Plausible analytics, and the auth scaffold for Google + Email. Marketing landing page completes to match the second screenshot Brock approved.

**Prerequisites:** Phase 0 closure pushed. Phase 1A is independent — does not need to be pushed first, but ideally is.

**Output:** Two scaffolded apps, shared design tokens, marketing landing page complete, Expo app boots with a placeholder dashboard. One or two clean commits.

---

## How to run

1. Confirm Phase 0 closure is on `main`
2. Open a fresh Claude Code session in `~/code/tyndale`
3. Copy everything between the `BEGIN` and `END` markers below
4. Paste into Claude Code
5. Review the commit(s) and the local dev experience; push manually after `npm run dev` works for both apps

---

```
BEGIN — Phase 1B Prompt

You are scaffolding Tyndale's two frontend apps: a universal Expo app (web + iOS
+ Android from one codebase) and a Next.js marketing landing.

CONTEXT
- Tech stack: React Native + Expo with Expo Router for the universal app
  (apps/mobile), Next.js with App Router for the marketing landing
  (apps/web-marketing). Phil is ramping on RN; assume the team can troubleshoot.
- Design system: dark navy/teal dashboard + cream-light marketing palette per
  the screenshots Brock approved. Inter font. Tyndale logo (SVG; you'll reuse
  the SVG from any of the spec HTMLs in docs/tyndale-spec/).
- Analytics: Plausible at launch. Privacy-respecting first-party only. No
  advertising or retargeting trackers ANYWHERE.
- Auth: Google + Email at V1-Lite launch. Apple Sign-In is fast-follow at
  native iOS App Store submission. Scaffold the auth structure now; real
  end-to-end auth wiring lands in Phase 2.
- Domain: tyndaleapp.net. Email via SendGrid.
- This is a SCAFFOLD. The "SCAFFOLD — not for real PHI" banner must be
  prominent on every page.
- Regulatory posture: non-HIPAA-covered consumer-health app. Don't claim
  HIPAA covered-entity status anywhere in the UI copy.

OUTPUTS

Two TypeScript apps inside the existing monorepo:

  apps/mobile/         — Expo Router universal RN app (web + iOS + Android)
  apps/web-marketing/  — Next.js App Router marketing landing

Plus shared design tokens in:

  packages/shared/src/design-tokens.ts

STEP 1 — packages/shared/src/design-tokens.ts

Create a TypeScript module exporting the Tyndale design tokens. Both apps
import from `@tyndale/shared`. Tokens to export:

  // Palette
  colors: {
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
    inkOnDark: { DEFAULT: '#FFFFFF', muted: 'rgba(255,255,255,0.78)', faint: 'rgba(255,255,255,0.55)' },
  },
  fonts: {
    sans: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
    mono: 'JetBrains Mono, ui-monospace, monospace',
  },
  radii: { sm: 8, md: 14, lg: 20 },
  shadows: {
    card: '0 1px 2px rgba(15, 42, 40, 0.04), 0 4px 12px rgba(15, 42, 40, 0.05)',
    elev: '0 2px 4px rgba(15, 42, 40, 0.05), 0 8px 24px rgba(15, 42, 40, 0.08)',
  },

Also export the Tyndale logo as an inline SVG string (extract from
docs/tyndale-spec/01_overview.html — search for `header-logo-mark`).

Update packages/shared/package.json to expose this module. Add the build
artifact pointer so other workspaces can import `@tyndale/shared/design-tokens`.

STEP 2 — apps/web-marketing (Next.js)

Initialize a Next.js 15 App Router project in apps/web-marketing.

Stack:
- next@15, react@19, typescript, tailwindcss, autoprefixer, postcss
- @tyndale/shared (workspace dep)
- next-auth@beta (Auth.js v5) — providers scaffolded but inactive until env
  vars present
- lucide-react for icons (matches the feature-card icon style in screenshot 2)

Tailwind config: import colors from @tyndale/shared/design-tokens via a small
shim, OR redeclare to match. Inter font via next/font/google.

Pages to build (App Router, all in apps/web-marketing/src/app/):

  app/layout.tsx       — root layout, Inter font, global metadata, Plausible
                         script tag (env-conditional — DEV doesn't load it)
  app/page.tsx         — the marketing landing (screenshot 2)
  app/privacy/page.tsx — placeholder; copy lands in Phase 7
  app/terms/page.tsx   — placeholder; copy lands in Phase 7

Marketing landing — match screenshot 2 in docs/tyndale-spec/01_overview.html
visual style (it's the same palette). Structure:

  Top section (dark teal/ink background):
    - Header bar: Tyndale logo (SVG from design-tokens) + wordmark left;
      "Sign In" button right (links to /signin, placeholder route)
    - Hero:
      - Pill chip: green dot + "AI-POWERED HEALTH PLATFORM" eyebrow
      - H1: "Tyndale. Welcome to the App."
      - Body: "Sign in with your Google account to get started. New users
        will be asked to complete a quick profile setup."
      - Primary CTA: "Sign up with Google" (Google color + G icon)
      - Secondary link: "Learn more →"

  Middle section (cream-light background):
    - Eyebrow chip: "FEATURES"
    - H2: "Simple. Fast. Secure."
    - Subtitle: "Everything you need to manage your health information in one
      place, designed to be easy for everyone."
    - 6 feature cards in a 3x2 grid (sage-tint icon backgrounds with white card
      bodies). Cards from screenshot 2:
        1. Easy Sign-In — "Log in with your Google account in one click. No
           extra passwords to create or remember."
        2. Simple to Use — "A clean, intuitive design that makes managing your
           health information quick and effortless."
        3. Insurance Card Scanner — "Snap a photo of your insurance card and
           we automatically read and save your coverage details."
        4. Your Data Stays Safe — "Your personal and health information is
           protected with industry-standard security at every step."
        5. AI Health Assistant — "Ask questions, review bills, or get
           guidance — our built-in assistant is here to help anytime."
        6. Always Up to Date — "See your coverage details, cost estimates,
           and account activity in real time."

  Bottom section (dark teal/ink background):
    - H2: "Built for you"
    - Subtitle: "Designed to work the way you expect — every time."
    - Three-column badge row:
        Fast / LOADS IN UNDER A SECOND
        Secure / ENCRYPTED & PROTECTED
        Reliable / ALWAYS AVAILABLE

  Footer:
    - Tyndale logo + small wordmark
    - Permanent disclaimer (one line, always present): "Tyndale provides
      medical billing and coverage advocacy, not medical, legal, or financial
      advice."
    - Links: Privacy · Terms · Contact
    - Tiny copyright: "© 2026 The Little Guy LLC. d/b/a Tyndale."
    - "SCAFFOLD — not for real PHI" banner pinned to the very top of every
      page (small amber bar with the text)

Accessibility:
- Semantic HTML (header, main, section, footer)
- Logical heading order
- Focus rings preserved on interactive elements
- Color contrast 4.5:1+ for body text on backgrounds

Auth scaffolding (Phase 2 wires real auth; Phase 1B just makes the structure
exist):

  apps/web-marketing/src/app/api/auth/[...nextauth]/route.ts
  apps/web-marketing/src/lib/auth.ts

  In auth.ts:
    - Import NextAuth and providers conditionally
    - Google provider: enabled only if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
      are present at runtime
    - Email provider: scaffolded for SendGrid-based magic links; inactive in
      Phase 1B
    - Apple provider: NOT WIRED in Phase 1B (fast-follow at iOS submission)
    - JWT session strategy (move to DB sessions in Phase 4)
    - AUTH_SECRET required in production; log a startup warning if missing
      in development

  apps/web-marketing/.env.example:
    NEXT_PUBLIC_API_BASE_URL=http://localhost:4000
    NEXT_PUBLIC_PLAUSIBLE_DOMAIN=tyndaleapp.net
    NEXT_PUBLIC_PLAUSIBLE_SCRIPT=https://plausible.io/js/script.js
    AUTH_URL=http://localhost:3000
    AUTH_SECRET=                     # openssl rand -base64 32
    GOOGLE_CLIENT_ID=
    GOOGLE_CLIENT_SECRET=

  /signin route is a placeholder showing "Sign in coming online in Phase 2"
  for now.

STEP 3 — apps/mobile (Expo)

Initialize an Expo project with Expo Router (file-based routing).

Stack:
- expo@latest, expo-router@latest
- react@19, react-native, react-native-web, react-dom
- typescript
- nativewind (Tailwind for RN; same Tailwind config shape as web)
- @tyndale/shared (workspace dep)
- expo-auth-session for Google + Email auth flows (scaffolded, not wired)
- @plausible-tracker/plausible-tracker for native + web client-side analytics

Expo config (app.config.ts):
- name: Tyndale
- scheme: tyndale
- web build target: static export
- iOS bundle identifier: net.tyndaleapp.app
- Android package: net.tyndaleapp.app
- Note in a comment: Apple Sign-In capability deferred to native iOS
  submission

Tailwind config (apps/mobile/tailwind.config.js):
- content: ./app/**/*.{ts,tsx}, ./components/**/*.{ts,tsx}
- theme.extend.colors: import from @tyndale/shared/design-tokens (or
  redeclare to match)
- Inter font via expo-font + the @expo/google-fonts/inter package

Routes (Expo Router, all in apps/mobile/app/):

  app/_layout.tsx          — root layout, font loading, Plausible init,
                             "SCAFFOLD — not for real PHI" banner pinned top
  app/(auth)/sign-in.tsx   — Google + Email sign-in stubs (placeholder UI)
  app/(app)/_layout.tsx    — authenticated layout (placeholder; real auth
                             gate lands in Phase 2)
  app/(app)/index.tsx      — dashboard placeholder: hero "Welcome back,
                             {firstName}." plus a centered message
                             "Dashboard coming online in Phase 2 — check the
                             Phase 0 spec for the full layout."
  app/(app)/settings.tsx   — placeholder for the improvement-consent toggle
                             (real toggle wires in Phase 4)

Dashboard placeholder uses the dark theme tokens (navy background, cream-on-
dark text). Settings uses the same tokens.

Auth scaffolding (Phase 2 wires real auth):

  apps/mobile/lib/auth.ts:
    - expo-auth-session config for Google
    - Email magic-link stub
    - Session token storage via expo-secure-store
    - No real OAuth round trip in Phase 1B — buttons render but routes are
      placeholders

apps/mobile/.env.example:
    EXPO_PUBLIC_API_BASE_URL=http://localhost:4000
    EXPO_PUBLIC_PLAUSIBLE_DOMAIN=tyndaleapp.net
    EXPO_PUBLIC_PLAUSIBLE_SCRIPT=https://plausible.io/js/script.js
    # Google OAuth client IDs are per-platform for Expo — fill in Phase 2
    EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=
    EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=
    EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=

STEP 4 — Plausible

In both apps, the Plausible script loads only when the
PLAUSIBLE_DOMAIN env var is non-empty AND the build is production. Dev does
not load the script (prevents skewing analytics with dev traffic).

Custom events to track from Phase 1B:
- `page_view` (default; automatic)
- `signin_clicked` (fires when "Sign up with Google" is clicked, even
  though auth isn't wired — useful baseline)

Add a small `apps/mobile/lib/analytics.ts` and
`apps/web-marketing/src/lib/analytics.ts` exposing a `track(eventName,
props?)` function. Both wrap the Plausible API.

STEP 5 — Local dev verification

From the repo root:

  npm install
  npm run dev -w @tyndale/web-marketing   # boots Next.js on :3000
  npm run dev -w @tyndale/mobile          # boots Expo on :8081 web target

Check:
- The marketing landing renders the full layout from Step 2
- The Expo web target renders the placeholder dashboard with the dark theme
- "SCAFFOLD — not for real PHI" banner appears on every page in both apps
- Tailwind utility classes resolve correctly
- TypeScript type-checks: `npx tsc --noEmit -p apps/web-marketing &&
  npx tsc --noEmit -p apps/mobile`
- No console errors in either app

If the Expo iOS/Android targets don't start (Phil may not have Xcode/Android
Studio set up yet), document that in the report-back but don't block on it
— the web target is what V1-Lite ships first.

STEP 6 — Commits

Two commits (or one if you prefer; two is cleaner):

Commit 1:
  git add packages/shared/
  git commit -m "feat(shared): design tokens + Tyndale logo"

Commit 2:
  git add apps/mobile/ apps/web-marketing/
  git commit -m "feat(frontend): Phase 1B scaffold — Expo + Next.js marketing landing"

DO NOT push. Show the commit log and a screenshot/description of the landing
page rendering. Phil reviews and pushes.

STEP 7 — REPORT BACK

In your reply, include:
- `git log --oneline -5`
- `git diff --stat HEAD~2`
- Confirmation that both apps boot via `npm run dev` and pages render
- Any deviation from this prompt and why
- Anything that needs my attention (especially: did the screenshot's visual
  match come out right? note any visual gaps so Phil can iterate)

DO NOT proceed beyond this prompt. The signed-in dashboard scaffold matching
screenshot 1 (coverage tiles, copay tiles, Amount Saved YTD, four quick
actions, Chat CTA) lands in Phase 2 when the runtime is up and we have real
data shapes to bind.

END — Phase 1B Prompt
```

---

## What this delivers

After Phase 1B executes and is pushed:

- `apps/web-marketing` renders the full marketing landing per screenshot 2 (dark hero with Google CTA, cream-light feature section with six cards, dark teal "Built for you" footer)
- `apps/mobile` Expo app boots on web, iOS, and Android targets with the dark dashboard theme applied
- Shared design tokens live in `@tyndale/shared/design-tokens` and both apps consume them
- Plausible script loads in production but stays out of dev — analytics events stub `signin_clicked` baseline ready
- Auth.js v5 (Next.js side) and expo-auth-session (mobile side) are scaffolded — Google provider conditional on env, Email magic link stub, Apple deferred per locked decision
- "SCAFFOLD — not for real PHI" banner is pinned to the top of every page in both apps
- TypeScript strict mode passes for both apps

## What's deferred to later phases

- **Real auth flows** → Phase 2 (after runtime exists for the FastAPI auth callbacks)
- **Signed-in dashboard per screenshot 1** (coverage tiles, copay tiles, Amount Saved YTD, four Skill quick-action tiles, Chat CTA) → Phase 2 (needs the runtime to return real-ish data)
- **Real Plausible events** for `bill_uploaded`, `audit_completed`, etc. → Phases 2–4 as features land
- **Apple Sign-In** → Fast-follow at native iOS App Store submission (post-V1-Lite launch)
- **Improvement-consent toggle in Settings** → Phase 4 (after the feedback loop spec is implemented)
- **Privacy and Terms pages** → Phase 7 (legal pack publication, after attorney sign-off)
