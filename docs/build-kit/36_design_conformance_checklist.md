# 36 · Design & UX Conformance Checklist
### For Phil — verify the built product against everything approved July 10–16 · 2026-08-03

**How to use:** every item is pass/fail against an exact expected value. Walk the live app + landing page with this open; mark ❌ anything that deviates and send back the ❌ list — don't fix silently, some deviations may be fine but that's Brock's call. Sources: `brock_to_phil_chatfirst_decisions_2026-07-10.md`, `claude_design_prompt_tyndale_flow.md` (both now in `research_companions/`), `33_orchestration_script.md`, the master handoff §A, and the approved palette decisions.

**Precedence (Brock 2026-08-18, A5):** the orchestration script (`33_orchestration_script.md`) is **doctrine**; this checklist is a **verification aid that conforms to it**. Where the two disagree, the conflict gets **flagged to Brock, never self-reconciled** by engineering — and the checklist row is amended to match the script once he rules.

**⚠️ One honesty note:** the approved v7 landing-page HTML mockup did not survive to disk (same working-folder failure as the script). Its approved values are encoded below as checklist items — they are the reference. If you want a pixel-level HTML reference regenerated, say so.

---

## A · Palette & design system (global)

| # | Check | Expected |
|---|---|---|
| A1 | Primary brand teal | **#3E5C57** — matched to the app login screen. Not any other green-teal. |
| A2 | Nav / header | Navy **#1D2A38** |
| A3 | Hero treatment | Navy → teal **gradient** (not flat) |
| A4 | Money / savings figures | Green **#2E7D5B** |
| A5 | Deductible / OOP figures | Amber family |
| A6 | Citations / source chips | Blue **#2C6E8F** |
| A7 | Page background | Cream **#FAF7F0** |
| A8 | Body text | **≥16px** everywhere, line height 1.5, sans-serif |
| A9 | Contrast | **≥4.5:1** all text |
| A10 | Tap targets | **≥44px** |
| A11 | Reading level | ~7th grade; underlines only for links |
| A12 | Layout | One column everywhere |

## B · Landing page

| # | Check | Expected |
|---|---|---|
| B1 | Headline | "Medical bills have more errors than you think. Tyndale finds them, and knows exactly how to resolve them" — *amended 2026-08-27 per Brock's 2026-08-18 ruling (B3 verbatim) + the conformance sweep rows; previous value: "Medical bills are full of errors. Find what's hiding in yours."* |
| B2 | Three-number example card | billed **$2,347.18** · insurer says **$1,184.60** · should actually owe **$612.40** — same numbers as the live app |
| B3 | Primary CTA | "Check my bill — free" — *amended 2026-08-27 per the 08-18 ruling + conformance sweep; previous value: "Check my bill".* |
| B4 | Savings band | **$504,100** figure present |
| B5 | Comparison band | "Not a chatbot with opinions" comparison present |
| B6 | Grounding band | The two-card grounding treatment (every claim sourced) |
| B7 | Our Story | **Small band across the page** labeled "Our Story" — NOT a large cofounder block with names/photos dominating (explicitly rejected) |
| B8 | Founders' story copy | The approved condensed verbatim text — no paraphrase |
| B9 | Footer disclaimer | "Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice." |
| B10 | No fake urgency | No countdown timers, no scarcity claims, anywhere |
| B11 | ⚠️ Marketing stat | **Nowhere** does the page claim "80% of medical bills contain errors" (unsupported figure — banned) |

## C · Upload

| # | Check | Expected |
|---|---|---|
| C1 | Camera-first | "Take a photo of your bill" + PDF upload — *amended 2026-08-27 to the shipped label (conformance sweep).* |
| C2 | Checklist chips | **Bill (required)** · EOB · Insurance card |
| C3 | Just-the-bill line | "Just have the bill? That works — I'll tell you what each extra document unlocks." |
| C4 | Trust microcopy | Lock icon + "Encrypted. Never sold. Used only for your audit." |
| C5 | Capture state | STATIC framing guide + review with "Use this photo / Retake" — *rewritten 2026-08-27: edge-detection framing was DELIBERATELY dropped (we don't detect document edges; an animated "locking on" overlay would be a decoration pretending to be a capability, and the review step makes no "looks readable" claim — we measure size/blur and warn on facts only, per the `capture.looks_good` registry comment). Do NOT "fix" this row by building fake edge detection.* |
| C6 | Record framing | Upload moment carries the "start of your file" copy (script §1.1) |

## D · Chat-first mechanics (D0–D7)

| # | Check | Expected |
|---|---|---|
| D1 | One status card | ONE card updating **in place** — not a stream of status bubbles |
| D2 | Stage bars | Four labeled bars filling **sequentially on real completion**: "Reading your bill → Checking each charge → Comparing your insurer's math → Writing your summary". **No fabricated percentages** |
| D3 | Leave-and-return | "This takes a few minutes — you can leave; I'll email you the moment it's ready." |
| D4 | Message discipline | Messages only on action/results/asks — status lives in the card (D2 minimal-chattiness) |
| D5 | Verification grouping | **≤3 verification cards per message** |
| D6 | Card anatomy | Plain-language line + three big buttons **Yes / No / Not sure** |
| D7 | Pre-select + confirm | Typed correction ("the second one never happened") → Tyndale maps it, marks the card, asks **one confirming tap**; the tap is the only thing that changes state; low-confidence → falls back to asking |
| D8 | "Not sure" honored | Never penalized; audits around it (script §4.4) |
| D9 | Cap collision | Tyndale-voiced (script §10.3) — **never** a raw rate-limit error |
| D10 | Errors | Odd-formatted fields warn-and-continue — never hard-block |

## E · The two moments

| # | Check | Expected |
|---|---|---|
| E1 | The reveal | Full-width, visually distinct card — **a MOMENT, not an ordinary bubble** |
| E2 | Three numbers | Stacked large; hero = "What you should actually owe: **$612.40**" |
| E3 | Gap callout | "**$572.20** less than your insurer's number" framing present |
| E4 | Findings | Each finding its own card: plain-English title, dollar impact, severity tag, **source line** ("source: your plan documents · published rates") |
| E5 | Complete-and-free | Findings complete before any paywall; "Complete — nothing held back" framing. Nothing teased |
| E6 | The unlock | Second distinct full-width card: "**$572.20 of this shouldn't be yours to pay.**" + resolution plan + "**$4.99, one time.**" |
| E7 | Unlock value list | ✓ call scripts ✓ deadlines tracked ✓ case stays open — + "One payment. No timers. Your audit stays free." |
| E8 | Subscription line | Understated: "Fixing bills often? Core is $14.99/mo." — no pressure treatment |

## F · The five newer chat states (master handoff §A2)

| # | Check | Expected |
|---|---|---|
| F1 | Attest-and-proceed | Name mismatch → relationship menu (7 options, **no** "none of the above, but let me in"), confirm line naming the patient, logged; **decline path** if refused (script §3.1–3.2) |
| F2 | Attest edge prompts | Teen sensitive-care, deceased/estate → **elevated prompts, not hard blocks** (§3.3–3.4). *Amended per Brock 2026-08-18 A5 — script governs: §3 authors teen + deceased only; the SUD-program prompt is removed from this row and from the product.* |
| F3 | Illegible/partial | Never renders a guessed number; names the unreadable part; asks for the one specific fix; runs what's readable (§5.1) |
| F4 | Summary-vs-itemized | Coaches getting the **itemized** bill + request script (§5.2) |
| F5 | Wrong document | Typed redirect naming what was detected ("that looks like a prescription label...") + what a bill/EOB looks like — **not** a generic `not_a_bill` dead-end (§5.3) |
| F6 | Conflicting data | **Reconcile-first ladder**: explain-the-difference confidently → ask for one missing input → provider/plan only as last resort, showing all three numbers (§5.4) |
| F7 | Fabrication decline | Warm decline + truthful reframe — never dead-ends (§10.1) |
| F8 | Guarantee decline | No prediction; cited base rate + strength-of-basis + next step (§10.2) |
| F9 | PACE handoff | Warm external-program handoff **keeping the case open** (§12) |

## G · Orchestration rendering (script §0 rules)

| # | Check | Expected |
|---|---|---|
| G1 | Verbatim | Strings match `33_orchestration_script.md` exactly — no paraphrase, no "snappier" edits |
| G2 | Variables | `{curly}` values are the only runtime substitution; all real computed values; missing value → §5 degradation variant, **never** a guess |
| G3 | `[B]` tier | Every legal/coverage string renders **with its citation chip** (blue #2C6E8F) — never sourceless |
| G4 | `[C]` tier | No strategy string predicts an outcome anywhere |
| G5 | Close-the-loop | Every "go get something" ends with the bring-it-back line + case stays open (= X1) |
| G6 | Nudges | +3d / +14d cadence wired, email-only at launch (no SMS) |

## H · Record, case page, resolution

| # | Check | Expected |
|---|---|---|
| H1 | Hierarchy | **Tyndale Record** (master, rolling 12-month lens) → **sub-cases** (one per service date) → each with permanent summary view + thread. Terminology: Phil's "case" = sub-case |
| H2 | Record rows | Provider, date, status chip ("Resolved — recovered $572" · "Waiting on insurer — due July 24" · "Needs your EOB") |
| H3 | Sub-case summary | Three numbers, findings w/ citations, live status + next expected event, recovery tally, "Continue the conversation" |
| H4 | Case page | Dark status banner: response-deadline clock, recovered-so-far, open items + what-each-unlocks, next check-in |
| H5 | Gameplan | Numbered plan "biggest wins first"; per-call script (when they pick up / the problem / the ask / get it in writing); "if they push back" branches |
| H6 | Call mode | Full-screen; XL type; pinned claim#/dollar strip; tap-to-dial; step-through; "How did it go?" → 3 routes ("They're fixing it 🎉 / They pushed back / I left a message") |
| H7 | Pushback route | "That's okay — expected, even" + steadfast next move (verified findings don't soften) |
| H8 | Continuous journey | Post-audit "what I keep doing for you" beat + Record identity framing (script §11) |
| H9 | Needs-something | Have/need checklist card (☑/☐) + how-to-get-it hints + inline Add-document + §8.3 close line |

## I · Entitlements (first-case boundary — D5 sign-off item 5)

| # | Check | Expected |
|---|---|---|
| I1 | $4.99 first case | Includes **full follow-through for that case**: open case, deadline clock, nudges, re-audit on new documents — the mocked case page is correct for $4.99 users |
| I2 | Subscription gating | Gates case **count** + ongoing/proactive features — **never mid-case abandonment** |
| I3 | Free tier | One audit: three numbers + findings, complete; resolution guidance is the $4.99 unlock |

---

## Sign-off
Return the ❌ list to Brock. Items where built ≠ approved get a deliberate call: fix, or amend the spec — never silent drift. This checklist supersedes memory of the July 10–16 threads; if something here contradicts what you believe was agreed, flag it rather than assume.
