# Cowork prompt — 2026-08-12 · Unblock the engineering queue

Copy everything below the line into Cowork.

---

Engineering has shipped everything that doesn't need you. What's left is blocked on
authoring and on Brock's judgment. Full detail with file paths:
`docs/build-kit/BROCK_ASKS_2026-08-12.md` — read it first; it's the input to this prompt.

**The one rule that governs this whole session:** you may DRAFT copy in the established
voice. You may NOT invent a fact, a statistic, a citation, a base rate, or a dollar figure.
Where an item needs a real-world number or a legal citation, produce the *question* for
Brock, not an answer. A fabricated statistic on a public page is the single worst failure
available to this product — three of the items below exist precisely because engineering
refused to ship invented numbers.

Work in order. Items 1–3 unblock CI; 4–5 unblock a build session; 6 is decisions only.

---

## 1 · The §10.2 no-base-rate variant (highest value single string)

`decline.guarantee_trio` currently CANNOT render. §10.2 requires a cited base rate
(`{base_rate}` / `{base_rate_source}`), we have none, and the renderer correctly degrades
rather than invent a success statistic. This is the **launch-default** path, not an edge case
— today, a user who asks "will I win?" gets a graceful-degradation line instead of your copy.

Author the honest no-base-rate variant: the version for "we don't have a cited rate for a
case like this yet," keeping the three legs that don't depend on one (strength-of-basis for
THIS case, and the concrete next step) and dropping the leg that does. Same voice, same
`[C]` discipline — no prediction, no odds, no promise.

**Deliverable:** a new key `decline.guarantee_trio_no_rate` in a new version of
`33_orchestration_script.md`.

## 2 · Eleven unauthored keys

These render in the product today carrying engineering-written text — no copy was invented,
but engineering voice is reaching users. §3.1 of the asks doc lists each with where it
renders. For each: author it in voice, or say "delete this beat" and engineering removes it.

Two are more than copy:
- **`attest.edge_substance`** — your checklist F2 expects a substance-use-program prompt;
  your script §3 authors only teen and deceased. The two documents disagree. Resolve which
  is right, then author or drop.
- **`decline.fabrication_reframe`** — your §10.1 ends on a colon that invites the finding.
  This is that continuation. Confirm the shape you want (it currently names the strongest
  real finding and its dollar amount).

## 3 · X-rules machine-readable definitions (`37_x_rules_contracts.md`)

X1 is built and enforcing in CI. **X2, X3 and X5 exist as typed stubs that raise** — so
nothing silently "passes" a rule we can't check. Draft the definitions:

- **X2** — finding ⇒ ≥1 action, or explicitly typed `informational_context`. What counts as
  an action; what marks a finding informational?
- **X3** — an incomplete-input figure must carry a qualifier naming the missing input. What
  is the qualifier's required shape?
- **X5** — an error finding needs `error_type` + implicated line items + dollar impact. **The
  `error_type` enum is the blocker** — the taxonomy has to come from you.

Draft as contracts an engineer can implement without a second conversation: for each rule,
what MUST be true, what makes it fail, and one worked failing example (X1's spec used
"To finish this check I need your EOB. Please upload it to continue." — that shape works
well).

## 4 · The round-2 delta inventory — keep/drop pass

`docs/design/round2_delta_inventory.md`, 30 rows, nothing applied. Engineering cannot start
the application session until rows are vetoed. The four `[conflict]` rows need Brock
specifically (asks doc §2). Two flags:

- **C1 is the load-bearing one.** Your prototype's upload copy promises "No EOBs needed —
  I'll pull your Explanation of Benefits automatically." That's coverage-connection: Full V1,
  post-launch, currently gated off. Engineering marked it DO-NOT-ADOPT-YET and kept
  uploads-first. It gates two other upload rows.
- **N7 is a design-system decision, not a component one.** The prototype's glassmorphism +
  ambient-aura language isn't expressible in the current token system (blur, layered
  translucency, gradient auras). Adopting it changes the token vocabulary.

**Deliverable:** keep / drop / defer against each row, with a one-line reason on anything
dropped.

## 5 · Landing-page copy gaps

The page is live on dev, built verbatim from your round-2 prototype. Three sections were
**held back** rather than shipped, because each carries an unsubstantiated claim:

- the four-stat band (74% / 19% / 100M+ / 45%) — "Sources: JAMA · KFF" is an attribution,
  not a citation
- "Use the $400 dispute right" — a Tier-B legal claim with no source
- the tips band — a subscription tease while billing is dark

**Do not resolve these by writing citations.** Produce the list of what must be sourced, per
claim, for Brock to supply or approve dropping. Then author what IS missing and doesn't need
a fact: `{itemized_request_script}` (§5.2's actual words for asking a billing office for an
itemized bill — the string that section exists to deliver, currently absent), plus any empty
or error states the landing needs.

## 6 · Decisions only Brock can make — do not draft answers

Put these to him and record the answers; generating a plausible answer here is worse than
leaving them open.

1. **Crisis routing.** Your §10.5 offers "I can share a few resources." Locked doctrine
   (DL-04) is a clean refusal with **no routing of any kind**. Both cannot be true.
   Engineering registered your copy but did not wire it; the clean decline still ships. Which
   governs?
2. **`$504,100` "recovered for members"** — live on the landing because checklist B4 requires
   it. Is it substantiated, and as of when? Your own beta band says "we're early."
3. **Headline** — checklist B1 vs the prototype's "Your medical bill is probably wrong."
   Checklist won. Which stands? (The prototype's is itself an unsupported claim about the
   reader's bill.)
4. **`[B]` tagging** — your header counts 4 `[B]`; the registry parses zero, because your
   four marks are dual `[A]/[B]`. Which specific keys are `[B]`? Naming even one turns the
   citation-chip enforcement on for real.
5. **A8 body size** — the app's body text is 14px against a ≥16px requirement. Changing it
   reflows every screen. Part of round 2, or its own pass?

---

## Output

- New copy → a new version of **`33_orchestration_script.md`** (never edits to the runtime
  registry — CI fails on drift and names the key; that's your §0 rule 1, now enforced).
- X-rules → **`37_x_rules_contracts.md`**.
- Delta pass → annotations on `round2_delta_inventory.md`.
- Decisions from §6 → **DL-NN entries in `docs/decision-log.md`**, in the usual format.

Anything you can't resolve without Brock, leave as a named open question rather than a guess.
