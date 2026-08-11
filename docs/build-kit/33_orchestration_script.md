# Tyndale Orchestration Script — v1

**What this is:** every system-authored message string the chat thread renders across the whole journey — acknowledgments, stage labels, verification intros, data-quality states, the reveal, the unlock, needs-documents asks, resolution/call copy, terminal states, and the continuous-journey beats. This is the D1 deliverable from the chat-first sign-off (`brock_to_phil_chatfirst_decisions_2026-07-10.md`): **we author the voice; Phil renders these verbatim; placeholder copy never reaches staging.** It is a doctrine file — it encodes the locked rules-logic and voice tiering as user-facing language.

**Status:** v1, for Brock sign-off → then to Phil as part of the Batch-A drop.

---

## 0 · Rendering rules (read first)

1. **Render verbatim.** These strings are the product's voice. Don't paraphrase, shorten, or "make it snappier" in code. Copy changes come as a new version of this file.
2. **Variables** are in `{curly_braces}` and are the ONLY thing that changes at runtime. Every variable is a real, computed/extracted value — never a guess (grounding doctrine). If a value isn't available, use the graceful-degradation variant in §5, don't invent it.
3. **Voice tiers** (tag shown as `[A]`/`[B]`/`[C]` — governs rendering, not shown to user):
   - `[A]` **Fact** — stated plainly (numbers, what a document says).
   - `[B]` **Legal/coverage claim** — must render with its citation chip; never appears without a source line. Language is calibrated to the law's strength (categorical vs. conditional).
   - `[C]` **Strategy/recommendation** — reasoned and qualified; **never predicts an outcome.** No "you'll win," "they'll refund you," odds as promises.
4. **Reading level ~7th grade, body ≥16px, calm and few.** Status lives in the updating card (§2), not in message spam.
5. **Never dead-end (graceful degradation).** Every "go get something" line ends by inviting the user to bring it back and pick up where they left off (close-the-loop, X1).
6. **Never predict outcomes; stay steadfast on verified findings.** A finding Tyndale verified doesn't soften because the user is anxious or a payer pushed back.

### Variable dictionary
`{first_name}` user's first name (fallback: "there") · `{patient_name}` name on the bill · `{payer}` insurer (e.g., "Blue Shield") · `{provider}` billing provider/facility · `{doc_list}` human list of received docs (e.g., "a bill and an EOB") · `{billed}` amount billed · `{eob_owed}` what the insurer says you owe · `{tyndale_owed}` what Tyndale computes you should owe · `{gap}` the difference worth pursuing · `{n_findings}` count of findings · `{finding_title}` / `{finding_amount}` / `{finding_source}` per finding · `{service_date}` · `{visit_desc}` plain-language visit description · `{line_desc}` plain-language line-item · `{deadline_date}` response deadline · `{doc_needed}` the specific missing document.

*Example values used in illustrations below (the live-site set): billed `$2,347.18` · insurer says `$1,184.60` · should actually owe `$612.40` · gap `$572.20`.*

---

## 1 · Upload + opening (the start of the file)

**1.1 Upload-moment framing** `[A]` *(continuous-journey principle — this is the start of their Record, not a one-off tool)*
> "This is the start of your file. I'll read what you upload, remember your plan, and keep watching what happens next — so you're not doing this alone."

**1.2 Trust microcopy (under the upload control)** `[A]`
> "Encrypted. Never sold. Used only for your audit."

**1.3 Just-the-bill reassurance** `[A]`
> "Just have the bill? That works — I'll tell you what each extra document unlocks."

**1.4 Opening acknowledgment (on submit)** `[A]`
> "Got your documents — {doc_list} from {payer}. Reading them now…"

*Single-doc variant:* "Got it — your bill from {provider}. Reading it now…"

---

## 2 · The status card (one card, updates in place)

**2.1 Stage labels (four sequential loading bars — fill on real completion only, never fabricated %)** `[A]`
> "Reading your bill" → "Checking each charge" → "Comparing your insurer's math" → "Writing your summary"

**2.2 Leave-and-come-back line (under the card)** `[A]`
> "This takes a few minutes — you can leave; I'll email you the moment it's ready."

**2.3 Long-wait line (if a stage runs unusually long)** `[A]`
> "Still working — this one's taking a little longer than usual. Nothing's wrong; I'd rather be right than fast. I'll email you the moment it's done."

---

## 3 · Attest-and-proceed — bill is for someone else (B5-6)

**3.1 Name mismatch — the authorization step** `[A]` *(relationship-first wording, LOCKED)*
> "This bill is for **{patient_name}**, and your account is registered to **{first_name}**. Quick check before I dig in — what's your relationship to {patient_name}?"
>
> Options: ○ Spouse/partner ○ Parent/legal guardian ○ Adult child or family caregiver ○ Agent under a healthcare power of attorney ○ Court-appointed guardian/conservator ○ Executor/administrator of {patient_name}'s estate ○ Other
>
> Confirm line (shown with the choice): "By continuing, I confirm I'm authorized to manage medical bills for {patient_name}. I understand Tyndale relies on this and keeps a permanent, timestamped record of it."

**3.2 If the user won't attest / says it isn't theirs to manage** `[A]` *(decline, never dead-end)*
> "No problem — I can only work on a bill when someone authorized to manage it asks me to. If {patient_name} wants to look at this, they can upload it from their own account and I'll take it from there."

**3.3 Elevated prompt — sensitive teen services** `[A]` *(edge case; prompt, not a block)*
> "One thing worth knowing: for some care, the law can give a teen sole say over their own records — even from a parent. If that applies here, {patient_name} may need to be the one to bring this to me. Want to continue, or have them take it from here?"

**3.4 Elevated prompt — deceased / estate** `[A]`
> "I'm sorry for your loss. I can help you sort this out. Heads-up for later: if we end up contacting the provider or insurer, they'll usually ask for estate paperwork before they'll make changes — I'll tell you exactly what, when we get there."

---

## 4 · Verification (confirm what happened — grouped, ≤3 cards per message)

**4.1 Verification intro** `[A]`
> "Before I audit, let's confirm what happened at your visit — {a few / three} quick ones:"

**4.2 Per-card line (plain-language, one line)** `[A]`
> "{visit_desc}" — e.g., "An MRI of your left knee — about 30 minutes in the scanner."
> Buttons: **Yes** · **No** · **Not sure**

**4.3 Pre-selected, awaiting-confirm state (user typed a correction)** `[A]`
> "Sounds like the {line_desc} — I've marked '{their answer}.' Tap confirm and I'll factor it in." [Confirm]

*Low-confidence fallback (if mapping is uncertain — don't guess which card):*
> "I want to mark the right one. Which of these did you mean?" [shows the candidate cards]

**4.4 "Not sure" handling** `[A]` *(input-dependence honesty, X3 — never penalize uncertainty)*
> "That's fine — 'not sure' is an honest answer. I'll audit around it and tell you if it's something worth pinning down later."

---

## 5 · Data-quality states (never guess — graceful degradation)

**5.1 Partial/illegible read (B5-1)** `[A]` *(never invent a number; run what's readable; ask for the one fix)*
> "I read most of this, but {line_desc} is too blurry for me to trust — and I won't guess at a number on your bill. A clearer photo of just that part fixes it. Everything else, I've got — here's what I can already tell you:"

**5.2 Summary vs. itemized coaching (B5-1)** `[A]`
> "This looks like a summary statement. The **itemized** bill is where errors actually hide — every code and charge, line by line. Here's how to ask for it: '{itemized_request_script}.' Bring it back and I'll pick up right where we left off."

**5.3 Wrong document (B5-2)** `[A]` *(redirect, never audit a non-bill)*
> "That looks like {detected_doc_type}, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**. Here's what each one looks like so you know what to grab:"

**5.4 Conflicting/impossible data — reconcile-first (B5-5)** `[A]/[C]`
Rung 0 — Tyndale explains the difference (confident answer, no escalation):
> "These two numbers look like they disagree — your bill says {billed} and your EOB says {eob_owed} — but they're actually measuring different things. {reconciliation_explanation}. So it's not an error; here's the real math."

Rung 1 — one missing input needed:
> "I can square these two numbers with one more piece: {doc_needed}. Grab that and I'll finish the reconciliation — you won't have to call anyone."

Rung 2 — genuinely can't reconcile (last resort):
> "I've tried every way to make these numbers line up and they still don't — and that gap is worth **{gap}** to you. That's your strongest question. Here's exactly what to ask {provider} and {payer} to explain it."

---

## 6 · The reveal (a MOMENT — full-width, distinct)

**6.1 Three-number hero** `[A]`
> Billed: **{billed}**
> {payer} says you owe: **{eob_owed}**
> **What you should actually owe: {tyndale_owed}**

**6.2 Findings header** `[A]`
> "I found {n_findings} problems. Nothing held back — here they are in full:"

**6.3 Per-finding card** `[A]` fact + `[B]` if it rests on a rule/law
> Title: "{finding_title}" (e.g., "You were charged twice for the same MRI")
> Impact: "**{finding_amount}**"
> Source line (always present — grounding doctrine): "source: {finding_source}" (e.g., "your plan documents · published rates")

**6.4 Completeness line** `[A]`
> "That's the complete audit — every charge checked against your plan and real prices. Nothing's teased or hidden."

---

## 7 · The unlock (the second moment — $4.99)

**7.1 Unlock card** `[A]`
> "**{gap} of this shouldn't be yours to pay.** Unlock your resolution plan — who to call, exactly what to say, and every deadline — **$4.99, one time.**"
> Value list: ✓ Every call script, written for you · ✓ Every deadline tracked · ✓ Your case stays open until it's resolved
> Reassurance: "One payment. No timers. Your audit stays free."

**7.2 Understated subscription line (no pressure)** `[A]`
> "Fixing bills often? Core is $14.99/mo — unlimited audits and every case followed through."

*No countdowns, no fake urgency, ever.*

---

## 8 · Needs-something state (have/need checklist)

**8.1 Intro** `[A]`
> "Here's what I found so far. To lock in the numbers I need {a couple of things / one more thing}:"

**8.2 Checklist card** `[A]`
> ☑ {have_doc} · ☐ **{doc_needed}** ("{how_to_get_it_hint}")

**8.3 Close-the-loop line (always closes a needs-state — X1)** `[A]`
> "Add them here whenever they arrive — I'll pick up right where we left off. I'm keeping this case open for you."

---

## 9 · Resolution plan + call mode (post-unlock)

**9.1 Gameplan intro** `[C]` *(strategy — reasoned, never predicts the result)*
> "Here's your plan — biggest wins first. I'll be right here for each one."

**9.2 Prioritized action card** `[A]` label + `[C]` framing
> "① Call {payer} — targets {finding_amount} · ② Call {provider}'s billing office — targets {finding_amount} · ③ If either pushes back — the escalation."

**9.3 Easy-ask-first escalation framing (B3-1 doctrine)** `[C]`
> "Start friendly and simple — most of these get fixed with one call. We only escalate if they push back, and I'll tell you exactly when and how."

**9.4 Call-mode "how did it go?"** `[A]`
> Options: "They're fixing it 🎉" · "They pushed back" · "I left a message"

**9.5 Pushback route** `[C]` *(steadfast — a verified finding stands)*
> "That's okay — expected, even. A 'no' on the first call doesn't mean you're wrong; the finding still holds. Here's the next move."

---

## 10 · Terminal & guardrail states

**10.1 Fabrication request — decline + truthful reframe (B5-3)** `[A]`
> "I can't say something happened if it didn't, or make a problem look bigger than it is — that would only weaken your case if anyone checks. But here's what *is* actually off about this bill, and it's a real, honest case you can make:"

**10.2 Guarantee/outcome demand — decline + honest trio (B5-4)** `[C]`
> "I won't promise you'll win — nobody honest can, and I won't guess with your money. What I can tell you: cases like this succeed **{base_rate}** of the time ({base_rate_source}), yours rests on **{strength_of_basis}**, and the best next step is **{next_step}**."

**10.3 Cap collision (rate limit mid-audit — never a raw error, D6)** `[A]`
> "Give me a few minutes to focus on your audit — I'm at capacity for a moment. I'll email you the second it's ready; nothing you've done is lost."

**10.4 Generic failure — never dead-end** `[A]`
> "Something on my end hiccuped — that's on me, not you, and nothing you uploaded is lost. Give it another moment, or I'll email you the moment I've got it working again."

**10.5 Distress / crisis (no refusal-pairing here — care first)** `[A]`
> "It sounds like you're carrying a lot right now, and that matters more than any bill. If you want, I'm here to keep working through this with you — and if you'd like to talk to someone, I can share a few resources."

---

## 11 · Continuous journey (what I keep doing for you)

**11.1 Post-audit "what I keep doing" beat** `[A]`
> "Even after today, I'm still on this: I'll watch your deadlines, re-check the numbers if a corrected bill or EOB shows up, and keep your Record up to date. You won't have to remember any of it — that's my job."

**11.2 Record identity (dashboard framing)** `[A]`
> "This is your Tyndale Record — every bill I've checked for you, what I recovered, and what I'm still watching."

**11.3 Deadline-watch nudge (email + in-thread)** `[A]`
> "Heads-up: {payer} has until **{deadline_date}** to respond on your case. I'm watching it — if they go quiet, I'll tell you the next move."

**11.4 Re-audit-on-new-document** `[A]`
> "A new {doc_needed} came in — I re-ran the numbers so everything's current. Here's what changed:"

**11.5 Contextual nudge cadence (+3d / +14d, then event-driven — locked)** `[A]`
> +3d: "Just checking in — still here whenever you're ready to make that first call. No rush."
> +14d: "Your case is still open and I'm still watching {deadline_date}. Want me to walk you through the first call?"

---

## 12 · PACE / external-program handoff (graceful degradation)

**12.1 Warm handoff when the best help is outside Tyndale** `[A]/[B]`
> "Honestly, the strongest move here isn't with me — it's **{program_name}**, which exists exactly for this ({program_source}). Here's how to reach them and what to ask. I'll keep your case open on my side so nothing slips while you do."

*(PACE = the program-routing pattern for populations/situations better served by an external program; render with the program's real citation, Tier B.)*

---

## Changelog
- **v1 (2026-07-16):** Initial full script. Sources: chat-first sign-off D0–D7 + design-pass feedback (`brock_to_phil_chatfirst_decisions_2026-07-10.md`), approved flow copy (`claude_design_prompt_tyndale_flow.md`), and locked rules-logic (`tyndale_rules_logic_locked_decisions.md`, Batches 1–5 incl. B5-1…B5-6). Voice-tier tags and grounding/close-the-loop/never-predict rules applied throughout.
- **Open for Brock sign-off:** (1) the §7 unlock line wording; (2) the §10.2 guarantee-decline phrasing; (3) the §3 attest strings (mirror the locked B5-6 wording). On approval → Batch-A drop to Phil.
