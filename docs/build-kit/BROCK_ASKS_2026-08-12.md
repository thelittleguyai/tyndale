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
