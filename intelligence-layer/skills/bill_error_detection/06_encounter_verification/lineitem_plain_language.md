# Line-item plain-language translation

**What this is.** Before trusting that a charged service happened, translate each line item
(code + descriptor + complexity/units) into plain language the user can evaluate from their
lived experience of the visit. This is how V1-Lite verifies the encounter without clinical
data.

**CRITICAL LINE — facts, not clinical judgment.** Translate the FACTUAL meaning of the code
("you were billed for the highest-complexity ER visit level, which usually means a long,
intensive workup with multiple tests"). NEVER ask the user for a CLINICAL JUDGMENT ("was
this necessary?", "did you need this?") — clinical-necessity questions are out of scope per
`intelligence-layer/reference/refusals.md`. Ask only what the user can know from being there.

**How to translate, by high-risk line-item type.**
- **E/M levels** → describe what the level implies about visit length/intensity ("a level-5
  office visit usually means a long, complex visit"). Ask if that matches.
- **Time-based codes** → state the time the code implies ("this code bills for 60 minutes").
  Ask roughly how long the service took.
- **Units / quantities** → state the count ("billed as 8 units"). Ask whether that many were done.
- **Add-on procedures** → name the extra procedure plainly. Ask if it happened.
- **Lab panels / tests** → name the test ("a comprehensive metabolic panel — a blood draw").
  Ask whether blood was drawn / the test was done.

**Voice.** Translations are Tier A facts about what the bill says. The user's confirmation
is what converts a mismatch into a finding — see `user_confirmation_flow.md`.

**Forward compatibility.** In full Tyndale, clinical encounter data augments/replaces this
step; this plain-language logic remains the fallback and produces the labels that validate
the automated version.
