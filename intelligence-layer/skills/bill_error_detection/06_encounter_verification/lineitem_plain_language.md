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

## Example scenarios per category (Phase 2L)

In addition to the plain-language translation, produce **3–5 example scenarios** of what a
typical patient would have experienced for this category of service. These help the user recall
what actually happened without parsing medical jargon. Examples are factual + experiential,
written in **second-person past tense** ("you'd typically have…"), and stay FAR away from
clinical judgment (no "should you have", "was this necessary", etc.).

Per category guidance:

- **E/M visits (office, ER, urgent care, inpatient):** duration, number of staff seen, types
  of questions asked, tests done, time in waiting/exam rooms, specific procedures (imaging,
  blood draw, IV).
  Example — "high-complexity ER visit (99285)":
  - You'd typically have spent at least 1–2 hours in the ER
  - You'd have been seen by multiple staff — likely a nurse, then a doctor, and possibly a specialist
  - You'd likely have had blood tests or imaging done
  - You may have had IV fluids or medications given
  - You may have been monitored for an extended period
- **Lab tests:** how the sample was collected (blood draw, urine, swab), where, whether results
  came in person or via portal.
  Example — "Comprehensive metabolic panel (80053)":
  - You'd have had blood drawn — usually from your arm
  - The blood was sent to a lab (not analyzed at the clinic)
  - You'd typically get results within a few days, often via patient portal or a follow-up call
- **Imaging:** which body part, scan duration, contrast dye (IV/oral), hold-still/hold-breath,
  whether you were gowned.
  Example — "MRI brain w/ + w/o contrast (70553)":
  - You'd have been in the scanner for about 30–60 minutes
  - You'd have been asked to lie very still
  - You'd have had an IV placed for contrast dye partway through
  - The machine would have been loud (earplugs/headphones offered)
- **Procedures + surgeries:** anesthesia type, recovery time, incisions, follow-up.
  Example — "Appendectomy (44970)":
  - You'd have been under general anesthesia
  - You'd have had small incisions (laparoscopic) or one larger one (open)
  - You'd have stayed in recovery for 1–2 hours after
  - You may have stayed overnight
- **Injections + infusions:** where given (arm, IV), monitoring after, what you felt.
  Example — "Influenza vaccine (G0008)":
  - You'd have had a quick injection in your upper arm
  - You may have felt a brief sting
  - You'd typically be sent home immediately with no monitoring
- **Supplies + DME:** whether you received the item, were fitted, were trained.
  Example — "CPAP machine (E0601)":
  - You'd have received the machine at home or from a respiratory therapist
  - You'd have been fitted for the mask
  - You'd have been taught how to clean and operate it

**HARD LINE (unchanged):** examples describe what HAPPENED, never whether it SHOULD have
happened or was NECESSARY. The user verifies FACTS; Tyndale never asks for clinical judgment.

**Number of examples:** aim for 3–5. More than 5 feels like a checklist and pressures false
confirmations. When uncertain about the category, produce a minimal 2–3 generic scenarios
rather than fabricate specifics — better to ask less than ask wrongly.
