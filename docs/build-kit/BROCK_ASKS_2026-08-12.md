# Asks for Brock — 2026-08-12

**How to use this:** answer inline. Most are one-liners; the ones that need authored copy say
so and name the exact key. Nothing here needs you to read code — every file path is given so
you can check the context if you want it, not because you have to.

**Why now:** three workstreams are stalled on these. §1 blocks CI checkers that currently
refuse to run. §2 blocks a 30-row application pass nobody can start. §3 is copy that's
rendering engineering placeholder text to users today.

---

## §1 · Blocking CI and code (answer these first)

### 1.1 The X-rules machine-readable definitions
`37_x_rules_contracts.md` is still owed. X1 is built and enforcing in CI
(`intelligence-layer/evals/doctrine/x1_close_the_loop.py`). **X2, X3 and X5 exist as typed
stubs that raise `NotImplementedError`** — deliberately, so nothing silently "passes" a rule
we can't check yet.

- **X2** — finding ⇒ ≥1 action, or explicitly typed `informational_context`. What exactly
  counts as an action, and what marks a finding informational?
- **X3** — a figure computed from incomplete inputs must carry a qualifier naming the missing
  input. What's the qualifier's required shape?
- **X5** — an error finding needs `error_type` + implicated line items + dollar impact. **We
  need the `error_type` enum itself** — that's the blocker.

> **Ask:** the three definitions, in whatever form is natural to you. We'll turn them into
> the checkers.

### 1.2 The crisis-routing conflict — a doctrine contradiction
Your script §10.5 says: *"…and if you'd like to talk to someone, I can share a few
resources."* Our locked doctrine (CLAUDE.md, DL-04) is a **clean refusal with no 988 referral
and no routing of any kind**.

These can't both be true. I registered your copy as `crisis_care_first` but **did not wire
it** — the crisis path still renders the DL-04 clean decline.

> **Ask:** does §10.5 supersede the no-routing doctrine, or should §10.5 change? This is the
> one item where I'd rather have your answer than a fast decision.

### 1.3 `[B]` voice-tier tagging (conformance G3)
Your header counts 42 `[A]` / 4 `[B]` / 8 `[C]`. Our registry parses **79 `[A]` / 5 `[C]` /
zero `[B]`**. The gap: your four `[B]` marks are *dual* (`[A]/[B]` on §6.3 per-finding and
§12.1 handoff), and tagging those keys `[B]` would make them render the graceful-degradation
variant instead — because a `[B]` string may only render **with** its citation chip, and the
code doesn't attach one on those paths yet.

> **Ask:** which specific keys should be `[B]`? Naming even one lets us wire its citation and
> turn the enforcement on for real.

---

## §2 · The round-2 delta inventory — a keep/drop pass

Full doc: `docs/design/round2_delta_inventory.md` — 30 rows comparing your round-2 prototype
against the shipped app. **Nothing has been applied.** Application is the next session and
needs your veto pass first. The four `[conflict]` rows need you specifically:

| | The question |
|---|---|
| **C1** | Your upload copy promises *"No EOBs needed — I'll pull your Explanation of Benefits from Blue Shield automatically."* That's the coverage-connection path: Full V1, post-launch, currently gated off. I've marked it **DO-NOT-ADOPT-YET** and kept uploads-first. **Confirm?** (It gates two other upload rows.) |
| **C2** | Verification "No" is coloured `severity-high` (alarm red) in the prototype. A "no" is the user telling us a charge is wrong — information, not an error. Keep it neutral? |
| **C3** | Finding impact renders as `−$389.00`. But the finding is worth **+$389 to the user**. Which sign convention? It's on every finding card. |
| **C4** | The prototype's three-numbers card has no zero-gap variant. On a clean bill we render the three numbers with **no** callout (rather than "$0.00 less than your insurer's number"). Confirm that's right. |

> **Ask:** keep/drop on the four above. The other 26 rows we can propose and you veto — but
> **N7 is worth your attention**: the prototype's glassmorphism + ambient-aura visual language
> isn't expressible in our current token system (it needs blur, layered translucency,
> gradient auras). That's a design-system decision, not a component change.

---

## §3 · Copy that doesn't exist yet (rendering placeholders today)

### 3.1 Eleven keys we render with no counterpart in your script
These are live in the product. When your v1 landed, none of them had an authored string, so
each kept the engineering text it already shipped with — **no copy was invented**, but
engineering voice is reaching users on all eleven. Each needs your copy, or your OK to delete
the beat:

| Key | Where it renders |
|---|---|
| `audit_start` | "I'm running the full audit now…" after verification |
| `verification_nudge` | when the user types instead of tapping a card |
| `verification_map_partial_fallback` | your §4.3 authors ONE low-confidence fallback; we render a second, partial one |
| `attest.edge_substance` | **see 3.2 — your checklist and script disagree** |
| `decline.fabrication_reframe` | your §10.1 ends on a colon that invites the finding; this renders that continuation |
| `call_script_opener_payer` · `call_script_opener_provider` · `call_script_get_it_in_writing` · `call_script_if_they_push_back` | the four per-call script beats — your §9 authors the plan and the framing, not these |
| `call_mode_intro` · `call_mode_outro` | entering and leaving call mode |
| `capture.prompt_bill` · `capture.prompt_card` · `capture.looks_good` · `capture.retake` · `capture.add_page` | **new 2026-08-12** — camera capture (see 3.6) |

### 3.6 Camera capture — five new keys, and one line of your prototype we did not build
Camera-first capture shipped (checklist C1 + C5, delta N1). Five keys carry its copy; all five are
engineering-written today and want your voice.

Two notes on the prototype's capture surface specifically:

1. **The hint "I'll frame the edges for you and check it's readable" is not buildable as written.**
   We don't detect document edges (the guide frame is a static target, not a tracker), and we make
   no readability claim. Both halves of that sentence would be promises the product doesn't keep.
2. **The green "Looks readable" badge is not shipped, deliberately.** It's an unconditional claim
   about the photo in your prototype. What we ship instead: a warning ONLY when we measured a real
   problem (the frame is below the resolution floor, or its Laplacian variance says it's soft), and
   otherwise nothing. Passing a sharpness check doesn't make a bill readable — glare, a cut-off
   corner, a thumb over the total and 6pt print all pass it and still fail OCR — so a "readable"
   badge contradicted by "I couldn't read this" two screens later costs more trust than it buys.
   The confirm button is the user accepting the photo, not us grading it.

> **Ask:** author the five, and confirm the no-badge call. If you want a positive signal on that
> screen, tell us what it should claim and we'll tell you whether it's checkable.

### 3.7 The audit-ready email — two bodies, engineering-written
Your §2.2 line ("you can close this — I'll email you the moment it's ready") was withheld because
we didn't send that email. **We do now.** It sends on both terminal outcomes, because a user who
left is waiting either way:

| When | Subject | Body |
|---|---|---|
| Review finished | "Your Tyndale review is ready" | "Your review is done — the numbers and everything I found are waiting for you." |
| Finished, needs a document | "One thing would finish your Tyndale review" | "I got as far as I could on your review. There's one document I still need before I can finish the numbers — it's listed in the app." |

Both are engineering-written and PHI-free **by construction** — nothing case-specific is
interpolated at all, only the sign-in link. That constraint is not stylistic: email lands in an
inbox we don't control, gets forwarded and indexed, so no amount, provider, date, claim number or
finding may appear. Anything you write here inherits that limit.

> **Ask:** author both, or tell us they're fine as-is. (Email copy has never been in the registry —
> the magic-link and nudge text live in code the same way. Say if you'd rather own it there.)

### 3.8 The nudge split — confirm we read your §11.5 right
Your §11.5 +3d/+14d copy is follow-through voice ("still here whenever you're ready to make that
first call"). The shipped nudge cron, older than your script, fires on a DIFFERENT premise: a case
blocked on a missing document. Putting your check-in copy on a document-chase email would tell
someone we need their SBC that they're "ready to make that first call" — so we split it:

| Nudge | Fires when | Body |
|---|---|---|
| **Chase** | audit blocked on a load-bearing document | engineering text naming the DOCUMENT TYPE (PHI-free; email chrome like the magic link — see 3.7) |
| **Check-in** | audit done + gameplan + no outcome reported yet | **your §11.5, verbatim from the registry.** +14d cites `{deadline_date}` from a persisted deadline only; with none, the +3d line renders instead (your §0 rule 2 — an email can't carry the in-thread degradation apology). Goes quiet once the user reports how a call went |

Both at +3d/+14d, email-only, one email per case per run (chase wins when both apply).

> **Ask:** confirm the split, or tell us §11.5 was meant to cover the chase too — in which case
> author the chase line and we'll swap it in.

### 3.9 §10.4's email clause — now true, plus one seed to approve
Your system_error line ends "…or I'll email you the moment I've got it working again." That
email exists now: when a system_error case later completes, a recovery notice sends (same flag
family as the audit-ready email — same promise class). Two things for you:

1. **The recovery email body** (engineering-written, PHI-free like 3.7): subject "Back up and
   running — your Tyndale review is ready", body "That hiccup on my end is fixed — your review
   finished, and everything I found is waiting for you." + sign-in link. Author or approve.
2. **The no-email variant** (`system_error_no_email`, eng seed): where the flag is off, your
   full §10.4 would promise an email that never sends, so the thread renders your line minus
   the clause: "…nothing you uploaded is lost. Give it another moment — I'm on it." Approve
   the trim, or author your own no-email version.


### 3.10 Your worked example leaked into a user-visible bill (caught + guarded, one ask)
The first full dev e2e sweep (2026-08-17) caught the translate agent doing the exact thing the
Grounding Doctrine forbids: on a **photographed** bill whose OCR text came back thin, it echoed
the worked example from `06_encounter_verification/lineitem_plain_language.md` — "MRI brain
w/ + w/o contrast (70553)" — into the case's PERSISTED line items. A fabricated charge, shown
as real, sourced from your teaching example. (We only caught it because 70553 doubles as a
fixture-leak marker in the harness — your example codes are accidentally perfect canaries.)

Engineering shipped a deterministic guard the same day: a line item whose base code appears in
**no** uploaded document's OCR text is dropped at the translate seam and logged; if everything
drops, the case degrades to the honest ask-for-a-clearer-photo path. No prompt change needed
for safety.

**The one ask:** add an explicit grounding line to that skill — e.g. "Translate only codes that
appear in the document. If a code is unreadable, say so — never substitute a code from these
examples." And keep the example codes AS-IS (70553 / A9579 / 36000 are the harness's canary
set); if you ever swap them, tell engineering so the canaries follow.


### 3.11 A voice state your script doesn't have: "complete — and one document would sharpen it"
Phil ruled on the SBC gate (2026-08-18, from the first full dev sweep): an audit **completes at
the achievable rung**. Missing coverage terms no longer park a case in needs-documents — the
cost-sharing figure ships as a RANGE with an X3 qualifier naming the missing input ("between
$X and $Y until I see your deductible"), and the have/need checklist appears on the FINISHED
audit re-framed as deepening it. Your script authors needs-documents ("to finish your audit…")
but has no state for *finished-and-improvable*. Two keys render as `[PLACEHOLDER-eng]` until
you author them (staging boot BLOCKS on placeholders, so these are yours before staging):

1. **`unlock_more.intro`** — the line above the checklist on a completed audit. Eng seed:
   "Your audit is done — and one more document would sharpen it. Add your plan's SBC and I can
   pin down the cost-sharing math exactly instead of ranging it."
2. **`unlock_more.item_hint`** — the one-liner above the items. Eng seed: "Already checked
   items are on file — anything unchecked deepens what I can verify."

Voice guidance we followed pending you: completion first, invitation second, zero "unfinished"
framing. The X3 qualifier text itself ("between … until I see your …") is engineering-owned
[A]-tier data narration, same class as the dollar figures — flag if you want it otherwise.


### 3.12 Settings grew up for test day — eight keys, none blocking (2026-08-19)
Phil's walkthrough found Settings half-real; we made it real. Eight NEW registry keys exist as
**client fallbacks only** — deliberately ABSENT from the registry (the capture-keys precedent:
absent keys can't block the staging boot the way `[PLACEHOLDER-eng]` does, and §3.11's pair
stays the only deliberate placeholder set). Author whenever; each ships with the engineering
fallback shown in parentheses:

**Notifications** (the toggle is real now — it gates reminders/check-ins ONLY; transactional
mail — audit-ready, recovery, magic links — never consults it. That split is load-bearing;
the copy must not promise more):
1. `settings.notifications_email_label` ("Email notifications")
2. `settings.notifications_email_description` ("Case updates always arrive — this controls
   reminders and check-ins.")
3. `settings.notifications_sms_label` ("SMS notifications")
4. `settings.notifications_sms_coming_soon` ("Coming soon")

**Plan documents** (the SBC's new home — uploaded once at the plan level, it satisfies the
SBC line on every case's checklist and feeds the cost-sharing math):
5. `settings.plan_documents_title` ("Plan documents")
6. `settings.plan_documents_description` ("Your Summary of Benefits and Coverage (SBC)
   describes your plan, not one bill — add it once here and every case can use it.")
7. `settings.plan_documents_empty` ("No plan documents yet.")
8. `settings.plan_documents_sbc_on_file` ("✓ SBC on file — your cases won't ask for it again")

Also for your §6 dashboards: preference changes emit `notification_pref_changed`
(email_notifications_enabled true/false), so opt-out rates are countable from day one.


### 3.2 The SUD edge prompt — your two documents disagree
Conformance checklist **F2** lists a substance-use-program prompt as an expected attest edge
case. Your script **§3 authors only teen and deceased**. We render an engineering-written SUD
prompt today.

> **Ask:** author it, or drop it from the checklist.

### 3.3 The guarantee decline can't render your §10.2
§10.2 requires a **cited base rate**: *"cases like this succeed **{base_rate}** of the time
({base_rate_source})…"*. We have no cited base rate, and inventing a success statistic is
exactly what that string exists to prevent — so it currently **degrades** rather than render.

> **Ask:** a no-base-rate variant of §10.2 — the honest version for "we don't have a rate for
> a case like this yet." This is the launch-default path, not an edge case.

### 3.4 One wrong-document string, four branches
Your §5.3 authors a single typed redirect using `{detected_doc_type}`. Our router has four
branches — insurance card, plan summary/SBC, clinical record, unplaceable — and all four
currently render your one string with their own detected type.

> **Ask:** is one string right, or do you want per-branch copy? (Same question for
> `handoff.pace`, which renders your generic §12.1 with `{program_name}` = PACE.)

### 3.5 Variables your strings use that aren't in your §0 dictionary
`{itemized_request_script}` (§5.2) · `{detected_doc_type}` (§5.3) ·
`{reconciliation_explanation}` (§5.4) · `{have_doc}` / `{how_to_get_it_hint}` (§8.2) ·
`{base_rate}` / `{base_rate_source}` / `{strength_of_basis}` / `{next_step}` (§10.2) ·
`{program_name}` / `{program_source}` (§12.1).

Two have no source of truth yet: **`{itemized_request_script}`** (the actual words to say when
asking for an itemized bill — §5.2's whole point) and **`{base_rate_source}`** (see 3.3).

> **Ask:** author `{itemized_request_script}`, and confirm the rest are computed values.

---

## §4 · The landing page — 14 asks from the round-2 port

The page is **live on dev** (`https://dev.tyndaleapp.net`), built from
`docs/design/prototype-round2/`. Copy is verbatim from your prototype. These are the deltas
and gaps I hit:

**Numbers that need substantiation before they can stay/ship**
1. **`$504,100` "recovered for members"** — shipped (checklist B4 requires it), but it's a
   public number for a pre-launch product, and your own beta band says *"we're early."* Is it
   substantiated, and as of when?
2. **The four-stat band — NOT shipped.** `74%` disputed-errors-corrected · `19%` denied /
   <1% appealed · `100M+` medical debt · `45%` no itemized bill in 30 days. Your source line
   is *"Sources: JAMA · KFF"* — that's an attribution, not a citation. **Per stat: which
   study, which year?** (Same gate that bans the 80% figure in B11.)
3. **"Use the $400 dispute right"** (tips band, not shipped) — that's a Tier-B legal claim.
   What's the citation?

**Checklist ↔ prototype conflicts (checklist won; confirm)**
4. **Headline** — checklist B1: *"Medical bills are full of errors. Find what's hiding in
   yours."* Your prototype: *"Your medical bill is probably wrong. Find what's hiding in
   it."* I shipped the checklist's. Which do you want? (Note the prototype's is itself an
   unsupported claim about the reader's specific bill.)
5. **CTA** — checklist "Check my bill"; prototype "Check my bill — free". I shipped the
   prototype's. Confirm.

**Sections I held back**
6. **The tips band** is a subscription tease (lock icons, "Unlock the full playbook") while
   billing is dark. Ship as a tease, or hold until billing is live?
7. **The "what brings you in today?" chooser** links to `/estimate`, `/find-doctor`,
   `/plan-visit` — post-core placeholders. Omit, or point all four at `/upload`?

**Smaller**
8. **`REMEMBERED_CASE` names "UnitedHealthcare Choice Plus"** in an illustrative card on a
   public page. Fine, or genericise?
9. **`sob-example.png`** isn't used by the landing — does it belong to the upload flow?
10. **Hero photo** — I put your atmospheric photo *behind* the A3 navy→teal gradient under a
    scrim, so the gradient still reads and hero copy keeps AA contrast. Or did you intend the
    photo to replace the gradient?
11. **Empty/error states** for the landing: none authored. Needed?
12. **Zero-gap reveal variant** — if the landing's example card ever shows a clean bill,
    there's no copy for it. (Same question as C4.)
13. **Body-size floor** — checklist A8 says body ≥16px. Your prototype's body copy is 15px; I
    promoted it to 16 on the landing. Confirm 16 is the floor.
14. **A8 in the app** — mobile body is currently **14px**, which fails A8. Changing it reflows
    every screen. Is that part of round 2, or its own pass?

---

## Reference

- Acceptance authority: `docs/build-kit/36_design_conformance_checklist.md`
- Live conformance state: `docs/design/conformance_sweep_2026-08-11.md` (**42 PASS · 3 FAIL ·
  1 DEFERRED · 2 PARTIAL · 22 N-A-YET**)
- Your script, as pulled in: `intelligence-layer/prompts/orchestration_script.md` — 84 keys,
  **zero placeholders**, each carrying a `<!-- §N.N -->` marker back to your file. A copy
  change must arrive as a **new version of `33_orchestration_script.md`**; CI fails on any
  edit made in the registry, naming the key (your §0 rule 1, now enforced).
- Palette: your checklist §A hexes are adopted and are the single source. Adopting A4
  (`#2E7D5B`) fixed a live accessibility bug — savings figures were rendering at 2.90:1,
  below AA, on the most important number in the product.
