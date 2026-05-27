# Task L08 — Mobile-friendly web app shell

**Phase:** L2 · V1-Lite new
**Who:** Brock + Claude Code (scaffold); Phil finishes (production)
**Estimated time:** 2 hours (scaffold)
**Depends on:** L01–L07

## What this task does

Scaffolds the mobile-friendly web app shell for V1-Lite — an upload-centric, responsive UI. Brock builds the scaffold with Claude Code to validate the UX and the upload flow; Phil hardens it for production (auth, security, accessibility, performance). The scaffold uses the Tyndale design system you already have.

## Important framing

This is a **scaffold for validation and handoff**, not the production app. It demonstrates the upload flow, the chat-anchored interaction, and the feedback capture points so Phil has a concrete starting point. Production concerns (real auth, secure file handling, HIPAA-compliant hosting, full accessibility) are Phil's.

## Prompt to paste into Claude Code

```
Scaffold a mobile-friendly web app shell for Tyndale V1-Lite. This is a
validation scaffold and handoff starting point — NOT the production app.
Phil will harden it.

First read:
- v1_lite/01_v1lite_scope_and_compatibility.html (for the design system
  colors, fonts, logo — reuse them exactly)
- feedback/capture_points.md (the feedback UX must be present)
- reference/principles.md (the UX should embody anticipation)

Build a responsive web app scaffold with these characteristics:

TECH:
- Use a modern, simple stack the engineering team can extend: a single
  React app (Vite) OR Next.js — your call, but document the choice and
  keep it minimal. No backend in this scaffold; mock the API responses.
- Mobile-first responsive. Must look right at 380px width AND on desktop.
- Use the Tyndale design system: cream #F5F1EA background, teal #1F4E4A
  primary, sage #3DAA7E positive, amber #E08A3C warnings, rose #C75252
  errors, Inter font, the Document-Circle-with-checkmark logo (SVG in
  the scope HTML — reuse it).

SCREENS (all mocked, no real backend):

1. Landing / value prop — what Tyndale does, "Upload your first bill"
   call to action. Mobile-friendly hero.

2. Upload flow — the core V1-Lite interaction:
   - Drag-and-drop on desktop, tap-to-upload / camera on mobile
   - Document type auto-detection (mock: classify as bill/EOB/card)
   - Upload progress + a friendly "reading your document" state
   - Low-confidence value confirmation UI: when extraction confidence is
     low, show "I read your deductible as $2,500 — is that right?" with
     a one-tap confirm/correct (this embodies P1 AND captures feedback)

3. Chat-anchored results — the conversation with the Lead Planner:
   - User's question + Tyndale's response
   - A worked example: the MRI bill scenario from the Overview doc
     (bill shows $1,200, actually owe $560)
   - Tier A facts asserted, Tier B legal claim with a citation chip,
     Tier C recommendation as a clear action card
   - THE THREE-NUMBER AUDIT DISPLAY: show what the provider billed, what
     the insurer's EOB says you owe, and what Tyndale independently
     computes you actually owe — with the gaps highlighted. This is the
     core of Tyndale's value; make it visually clear which gaps are
     provider-side vs payer-side.
   - ENCOUNTER VERIFICATION UI (per Task L07): a lightweight, scannable
     checklist of the billed line items translated to plain language,
     each with one-tap "yes, that's right" / "no, that didn't happen" /
     "not sure". The "not sure" option must be real — never force a
     confirmation. Frame it as Tyndale double-checking on the user's
     behalf, not interrogating them.
   - Since V1-Lite defers letter generation: the recommendation is a
     SCRIPTED ACTION ("Call UnitedHealthcare at the number on your card,
     reference claim #X, and say...") with a copy-to-clipboard button —
     NOT a generated letter
   - Thumbs up/down on the response + "what was wrong?" picker on thumbs-down

4. Case tracker — a simple list of the user's open issues with deadlines
   (surfaces P2: what's next), showing the Proactive Monitor's tracked
   deadlines (mocked)

5. Settings — including the improvement-consent toggle (opt-in, OFF by
   default, with the copy from feedback/consent_model.md)

6. Outcome follow-up — a lightweight "Did this get resolved?" prompt
   (mock as a card that could appear in the tracker)

CONSTRAINTS:
- Put it in a new directory web_app_scaffold/ at the repo root
- Add web_app_scaffold/README.md explaining: this is a validation
  scaffold, what's mocked, what Phil needs to build for production
  (real auth, secure HIPAA-compliant file upload, real API integration,
  full WCAG accessibility audit, performance, error states)
- Mark MODES.md: web_app_scaffold/ is mode: v1-lite (full adds the
  connect-insurance flow and letter review/approval screens)
- Do NOT implement real authentication, real file storage, or real PHI
  handling in the scaffold. Mock everything. Add a prominent banner in
  the scaffold: "SCAFFOLD — not for real PHI."

Make the upload flow and the chat-anchored results genuinely good —
those are the two screens that prove the V1-Lite UX. The others can be
lighter.

Commit with message "Add mobile-friendly V1-Lite web app scaffold".
```

## Done when

- `web_app_scaffold/` exists with the screens
- It's responsive (works at 380px and desktop)
- It uses the Tyndale design system
- The upload flow includes the low-confidence confirmation UX
- The results screen shows a scripted action (not a generated letter)
- Feedback capture points are present
- The "SCAFFOLD — not for real PHI" banner is prominent
- README explains what Phil needs to do for production
- Git log shows the commit

## Handoff note

When Phil picks this up: this scaffold validates the UX and the flow. Production needs real auth, HIPAA-compliant hosting and file handling, a real backend wired to the FastAPI app, full accessibility, and proper error/loading states. The scaffold is the design target, not the codebase to ship.

## Next task

[Task L09 — V1-Lite handoff brief & upgrade map](L09_v1lite_handoff.md)
