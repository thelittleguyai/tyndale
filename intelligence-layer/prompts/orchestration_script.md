---
name: orchestration_script
description: |
  Versioned registry of every system-authored string the chat-first audit thread renders
  (Brock 2026-07-10, DL-91). The runtime renders these values VERBATIM — engineering never
  copy-edits them. Authoring is Brock's side; engineering owns only the loader + this key
  registry + the source mapping.
version: 1.0.0
source: docs/build-kit/33_orchestration_script.md (v1, 2026-07-16)
---

# Orchestration script — chat-first audit thread

**Every value below is Brock's authored copy, verbatim, from
`docs/build-kit/33_orchestration_script.md`.** Each key carries a `<!-- §N.N -->` marker
naming the section it came from, so a future version of his file drops in mechanically.
Copy changes arrive as a NEW VERSION OF HIS FILE — never as an edit here (his §0 rule 1,
now enforced by `tests/test_script_drift.py`, which fails CI naming the offending key).

## Rendering rules (his §0, enforced in code)

1. **Verbatim.** No paraphrase, no shortening, no "snappier" edits.
2. **Variables** are the ONLY runtime substitution and use `{single_braces}` (his
   convention; the legacy `{{double}}` form still parses). A variable with no value renders
   the **§5 degradation variant** — never a guess, never an empty string, never a raw
   `{token}` (`app.agents.context_loader.orchestration_step`).
3. **Voice tiers** `[A]`/`[B]`/`[C]` lead the value, govern rendering, and are never shown:
   - `[A]` fact — renders plainly.
   - `[B]` legal/coverage claim — renders ONLY with its citation chip; without one the
     graceful-degradation variant renders instead and a `doctrine_violation` is counted.
   - `[C]` strategy — never predicts an outcome; the loader refuses to boot a `[C]` value
     carrying a prediction variable.

## Variable dictionary (his §0)

`{first_name}` user's first name (fallback: "there") · `{patient_name}` name on the bill ·
`{payer}` insurer · `{provider}` billing provider/facility · `{doc_list}` human list of
received docs · `{billed}` amount billed · `{eob_owed}` what the insurer says you owe ·
`{tyndale_owed}` what Tyndale computes you should owe · `{gap}` the difference worth
pursuing · `{n_findings}` count of findings · `{finding_title}` / `{finding_amount}` /
`{finding_source}` per finding · `{service_date}` · `{visit_desc}` plain-language visit
description · `{line_desc}` plain-language line-item · `{deadline_date}` response deadline ·
`{doc_needed}` the specific missing document.

Additional variables his strings use, not in the §0 dictionary (flagged for him):
`{itemized_request_script}` (§5.2) · `{detected_doc_type}` (§5.3) ·
`{reconciliation_explanation}` (§5.4) · `{have_doc}` / `{how_to_get_it_hint}` (§8.2) ·
`{base_rate}` / `{base_rate_source}` / `{strength_of_basis}` / `{next_step}` (§10.2) ·
`{program_name}` / `{program_source}` (§12.1).

## §1 · Upload + opening

## record_first_upload_frame
<!-- §1.1 -->
[A] "This is the start of your file. I'll read what you upload, remember your plan, and keep watching what happens next — so you're not doing this alone."

## upload_trust_microcopy
<!-- §1.2 (new key) -->
[A] "Encrypted. Never sold. Used only for your audit."

## upload_just_the_bill
<!-- §1.3 (new key) -->
[A] "Just have the bill? That works — I'll tell you what each extra document unlocks."

## acknowledgment
<!-- §1.4 -->
[A] "Got your documents — {doc_list} from {payer}. Reading them now…"

## acknowledgment_single_doc
<!-- §1.4 single-doc variant (new key) -->
[A] "Got it — your bill from {provider}. Reading it now…"

## §2 · The status card

## stage_label_extraction
<!-- §2.1 bar 1 -->
[A] Reading your bill

## stage_label_translate
<!-- §2.1 bar 2 -->
[A] Checking each charge

## stage_label_encounter
<!-- §2.1 bar 3 -->
[A] Comparing your insurer's math

## stage_label_audit
<!-- §2.1 bar 4 -->
[A] Writing your summary

## status_leave_and_return
<!-- §2.2 (new key) -->
[A] "This takes a few minutes — you can leave; I'll email you the moment it's ready."

## long_wait
<!-- §2.3 -->
[A] "Still working — this one's taking a little longer than usual. Nothing's wrong; I'd rather be right than fast. I'll email you the moment it's done."

## §3 · Attest-and-proceed

## attest.intro
<!-- §3.1 -->
[A] "This bill is for **{patient_name}**, and your account is registered to **{first_name}**. Quick check before I dig in — what's your relationship to {patient_name}?"

## attest.confirm
<!-- §3.1 confirm line -->
[A] "By continuing, I confirm I'm authorized to manage medical bills for {patient_name}. I understand Tyndale relies on this and keeps a permanent, timestamped record of it."

## attest.menu_spouse_partner
<!-- §3.1 option 1 -->
[A] Spouse/partner

## attest.menu_parent_guardian
<!-- §3.1 option 2 (new key) -->
[A] Parent/legal guardian

## attest.menu_adult_child_caregiver
<!-- §3.1 option 3 (new key) -->
[A] Adult child or family caregiver

## attest.menu_healthcare_poa
<!-- §3.1 option 4 (new key) -->
[A] Agent under a healthcare power of attorney

## attest.menu_court_guardian
<!-- §3.1 option 5 (new key) -->
[A] Court-appointed guardian/conservator

## attest.menu_executor
<!-- §3.1 option 6 (new key) -->
[A] Executor/administrator of {patient_name}'s estate

## attest.menu_other
<!-- §3.1 option 7 (new key) -->
[A] Other

## attest.decline_ack
<!-- §3.2 -->
[A] "No problem — I can only work on a bill when someone authorized to manage it asks me to. If {patient_name} wants to look at this, they can upload it from their own account and I'll take it from there."

## attest.edge_teen
<!-- §3.3 -->
[A] "One thing worth knowing: for some care, the law can give a teen sole say over their own records — even from a parent. If that applies here, {patient_name} may need to be the one to bring this to me. Want to continue, or have them take it from here?"

## attest.edge_deceased
<!-- §3.4 -->
[A] "I'm sorry for your loss. I can help you sort this out. Heads-up for later: if we end up contacting the provider or insurer, they'll usually ask for estate paperwork before they'll make changes — I'll tell you exactly what, when we get there."

## §4 · Verification

## verification_intro
<!-- §4.1 -->
[A] "Before I audit, let's confirm what happened at your visit — {a few / three} quick ones:"

## verification_card_line
<!-- §4.2 (new key) -->
[A] "{visit_desc}"

## verification_map_confirm
<!-- §4.3 -->
[A] "Sounds like the {line_desc} — I've marked '{their_answer}.' Tap confirm and I'll factor it in."

## verification_map_fallback
<!-- §4.3 low-confidence fallback -->
[A] "I want to mark the right one. Which of these did you mean?"

## verification_not_sure
<!-- §4.4 (new key) -->
[A] "That's fine — 'not sure' is an honest answer. I'll audit around it and tell you if it's something worth pinning down later."

## §5 · Data-quality states (graceful degradation)

## dataquality_partial_illegible
<!-- §5.1 (new key) -->
[A] "I read most of this, but {line_desc} is too blurry for me to trust — and I won't guess at a number on your bill. A clearer photo of just that part fixes it. Everything else, I've got — here's what I can already tell you:"

## dataquality_summary_not_itemized
<!-- §5.2 (new key) -->
[A] "This looks like a summary statement. The **itemized** bill is where errors actually hide — every code and charge, line by line. Here's how to ask for it: '{itemized_request_script}.' Bring it back and I'll pick up right where we left off."

## wrongdoc.unknown
<!-- §5.3 — his ONE typed-redirect string; see the mapping note for the card/sbc/clinical branches -->
[A] "That looks like {detected_doc_type}, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**. Here's what each one looks like so you know what to grab:"

## wrongdoc.card
<!-- §5.3 — BORROWED: his script authors one wrong-document string, our router has four branches. Renders §5.3 with {detected_doc_type}. Brock: author per-branch copy if you want them distinct. -->
[A] "That looks like {detected_doc_type}, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**. Here's what each one looks like so you know what to grab:"

## wrongdoc.sbc
<!-- §5.3 — BORROWED (see wrongdoc.card note) -->
[A] "That looks like {detected_doc_type}, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**. Here's what each one looks like so you know what to grab:"

## wrongdoc.clinical
<!-- §5.3 — BORROWED (see wrongdoc.card note) -->
[A] "That looks like {detected_doc_type}, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**. Here's what each one looks like so you know what to grab:"

## reconcile.explain
<!-- §5.4 rung 0 -->
[A] "These two numbers look like they disagree — your bill says {billed} and your EOB says {eob_owed} — but they're actually measuring different things. {reconciliation_explanation}. So it's not an error; here's the real math."

## reconcile.ask_one_input
<!-- §5.4 rung 1 -->
[A] "I can square these two numbers with one more piece: {doc_needed}. Grab that and I'll finish the reconciliation — you won't have to call anyone."

## reconcile.last_resort
<!-- §5.4 rung 2 -->
[C] "I've tried every way to make these numbers line up and they still don't — and that gap is worth **{gap}** to you. That's your strongest question. Here's exactly what to ask {provider} and {payer} to explain it."

## §6 · The reveal

## three_number_reveal
<!-- §6.1 -->
[A] Billed: **{billed}**
{payer} says you owe: **{eob_owed}**
**What you should actually owe: {tyndale_owed}**

## findings_header
<!-- §6.2 (new key) -->
[A] "I found {n_findings} problems. Nothing held back — here they are in full:"

## finding_card_source
<!-- §6.3 source line (new key) -->
[A] "source: {finding_source}"

## completion
<!-- §6.4 -->
[A] "That's the complete audit — every charge checked against your plan and real prices. Nothing's teased or hidden."

## §7 · The unlock

## unlock.card
<!-- §7.1 (new key) -->
[A] "**{gap} of this shouldn't be yours to pay.** Unlock your resolution plan — who to call, exactly what to say, and every deadline — **$4.99, one time.**"

## unlock.value_list
<!-- §7.1 value list (new key) -->
[A] ✓ Every call script, written for you · ✓ Every deadline tracked · ✓ Your case stays open until it's resolved

## unlock.reassurance
<!-- §7.1 reassurance (new key) -->
[A] "One payment. No timers. Your audit stays free."

## unlock.subscription
<!-- §7.2 (new key) -->
[A] "Fixing bills often? Core is $14.99/mo — unlimited audits and every case followed through."

## §8 · Needs-something state

## needs_documents_intro
<!-- §8.1 -->
[A] "Here's what I found so far. To lock in the numbers I need {a couple of things / one more thing}:"

## needs_documents_item
<!-- §8.2 -->
[A] ☑ {have_doc} · ☐ **{doc_needed}** ("{how_to_get_it_hint}")

## needs_documents_close
<!-- §8.3 (new key) -->
[A] "Add them here whenever they arrive — I'll pick up right where we left off. I'm keeping this case open for you."

## §9 · Resolution plan + call mode

## gameplan.intro
<!-- §9.1 (new key) -->
[C] "Here's your plan — biggest wins first. I'll be right here for each one."

## gameplan.action_card
<!-- §9.2 (new key) -->
[A] "① Call {payer} — targets {finding_amount} · ② Call {provider}'s billing office — targets {finding_amount} · ③ If either pushes back — the escalation."

## gameplan.escalation_framing
<!-- §9.3 (new key) -->
[C] "Start friendly and simple — most of these get fixed with one call. We only escalate if they push back, and I'll tell you exactly when and how."

## call_mode.how_did_it_go
<!-- §9.4 (new key) -->
[A] "They're fixing it 🎉" · "They pushed back" · "I left a message"

## call_mode.pushback
<!-- §9.5 (new key) -->
[C] "That's okay — expected, even. A 'no' on the first call doesn't mean you're wrong; the finding still holds. Here's the next move."

## §10 · Terminal & guardrail states

## decline.fabrication
<!-- §10.1 -->
[A] "I can't say something happened if it didn't, or make a problem look bigger than it is — that would only weaken your case if anyone checks. But here's what *is* actually off about this bill, and it's a real, honest case you can make:"

## decline.guarantee_trio
<!-- §10.2 -->
[C] "I won't promise you'll win — nobody honest can, and I won't guess with your money. What I can tell you: cases like this succeed **{base_rate}** of the time ({base_rate_source}), yours rests on **{strength_of_basis}**, and the best next step is **{next_step}**."

## cap_collision
<!-- §10.3 -->
[A] "Give me a few minutes to focus on your audit — I'm at capacity for a moment. I'll email you the second it's ready; nothing you've done is lost."

## system_error
<!-- §10.4 -->
[A] "Something on my end hiccuped — that's on me, not you, and nothing you uploaded is lost. Give it another moment, or I'll email you the moment I've got it working again."

## system_error_no_email
<!-- UNMAPPED — §10.4 minus its email clause, rendered while enable_audit_ready_email is off
     (where the promise would be false). Engineering seed derived from his §10.4; asks §3.9.
     With the flag on, his full string renders and the recovery email actually sends. -->
[A] "Something on my end hiccuped — that's on me, not you, and nothing you uploaded is lost. Give it another moment — I'm on it."

## unlock_more.intro
<!-- §8.4 — v1.1 (Brock 2026-08-18 §1): the rung-2 complete-and-improvable state. -->
[A] "That's your complete audit — every charge checked. One thing would make the numbers sharper: your plan's Summary of Benefits. With it I can name your exact share instead of a close range."

## unlock_more.item_hint
<!-- §8.5 — v1.1 (Brock 2026-08-18 §1). -->
[A] "Everything checked is already on file. Each unchecked one is optional — and adds something more I can verify."

## §11 · Continuous journey

## record_post_audit_keep_doing
<!-- §11.1 -->
[A] "Even after today, I'm still on this: I'll watch your deadlines, re-check the numbers if a corrected bill or EOB shows up, and keep your Record up to date. You won't have to remember any of it — that's my job."

## record_identity
<!-- §11.2 (new key) -->
[A] "This is your Tyndale Record — every bill I've checked for you, what I recovered, and what I'm still watching."

## deadline_watch_nudge
<!-- §11.3 (new key) -->
[A] "Heads-up: {payer} has until **{deadline_date}** to respond on your case. I'm watching it — if they go quiet, I'll tell you the next move."

## reaudit_announce
<!-- §11.4 -->
[A] "A new {doc_needed} came in — I re-ran the numbers so everything's current. Here's what changed:"

## nudge.plus_3d
<!-- §11.5 +3d (new key) -->
[A] "Just checking in — still here whenever you're ready to make that first call. No rush."

## nudge.plus_14d
<!-- §11.5 +14d (new key) -->
[A] "Your case is still open and I'm still watching {deadline_date}. Want me to walk you through the first call?"

## §12 · External-program handoff

## handoff.generic_program
<!-- §12.1 -->
[A] "Honestly, the strongest move here isn't with me — it's **{program_name}**, which exists exactly for this ({program_source}). Here's how to reach them and what to ask. I'll keep your case open on my side so nothing slips while you do."

## handoff.pace
<!-- §12.1 — BORROWED: his script authors one program-handoff string; PACE is the named instance
     ({program_name} = PACE). Brock: author PACE-specific copy if you want it distinct. -->
[A] "Honestly, the strongest move here isn't with me — it's **{program_name}**, which exists exactly for this ({program_source}). Here's how to reach them and what to ask. I'll keep your case open on my side so nothing slips while you do."

## §E · Engineering-owned keys (NOT Brock's voice)

These are rendering mechanism, not product voice: an LLM instruction and the `[B]`-without-
citation fallback. They are engineering-authored by design and are excluded from the
drift guard (nothing in his file to compare against).

## generic_degraded
<!-- ENG — the [B]-without-citation fallback required by his §0 rule 3 -->
[A] I can't show you the exact rule text behind this yet — I've flagged it and I'll follow up with the citation.

## record_welcome_summary_instructions
<!-- ENG — an LLM system prompt, never rendered to a user -->
[A] You write the dashboard's one-line status summary. HARD RULES: state only facts derivable from the case states given; never mention a person, reviewer, team, agent, specialist, or any human/process step; never promise who does what next or when; never say anyone is "processing", "reviewing", or will "pick things up". Frame anything the USER can do plainly (e.g. "re-upload clearer copies"). At most two short sentences, plain text, no medical/legal/financial advice.

## record_welcome_summary_fallback
<!-- ENG — deterministic fallback when the summary LLM is unavailable -->
[A] You have {total} open cases — {breakdown}.

## access_request.intro
<!-- ENG — statutory access/deletion intake (§A2 state 5 stub); no counterpart in his script -->
[A] You can ask what Tyndale holds about a person, ask for it to be deleted, or ask for a correction. Tell me who the request is about and how to reach you. To be straight with you about what happens next: this records the request and a person follows up — I can't look anything up or confirm anything about a record from here.

## access_request.received
<!-- ENG — statutory access/deletion receipt; no counterpart in his script -->
[A] Your request has been recorded and someone will follow up at the contact you gave. I'm not able to tell you anything about what may or may not be held — that comes with the follow-up, once the request has been verified.

## §U · UNMAPPED — rendered today, no counterpart in Brock's v1

Each key below is rendered by a live code path but has NO authored string in
`33_orchestration_script.md` v1. Per the pull-in rule, **no copy was invented**: each keeps
the engineering text it already shipped with, and every one is listed in the session summary
for Brock to author or to confirm the beat should be dropped. They are excluded from the
drift guard (nothing to compare against).

## audit_start
<!-- UNMAPPED — no §2/§4 counterpart (his status card carries stage state instead) -->
[A] Thanks. I'm running the full audit now — I'll compute what you should owe and check it against the bill and your insurer.

## verification_nudge
<!-- UNMAPPED — no §4 counterpart -->
[A] Tap one of the buttons on a card above to answer — that's all I need here.

## verification_map_partial_fallback
<!-- UNMAPPED — his §4.3 authors ONE low-confidence fallback; we render a second, partial one -->
[A] I caught part of that but want to be sure I don't guess — please tap the answer on each card above.

## decline.fabrication_reframe
<!-- UNMAPPED — his §10.1 ends on a colon that INVITES the finding; this renders that continuation -->
[A] Here's the thing: you don't need it. What you actually have is stronger — {finding}, worth about ${amount}. That's checkable, it's on their own paperwork, and it's the argument I'd put in front of them.

## access_request.settings_label
<!-- UNMAPPED — the statutory-rights intake had a route and an encrypted event but NO way in
     from the app (deep review, finding 4). These six carry the settings row + form. Engineering
     text, listed for Brock: it's the entry point to a legal right, so the wording matters more
     than most. `access_request.intro`/`.received` already exist in §E and are unchanged. -->
[A] Privacy requests — access or delete data for someone named on a bill

## access_request.form_type_label
<!-- UNMAPPED — see access_request.settings_label -->
[A] What are you asking for?

## access_request.form_name_label
<!-- UNMAPPED — whose data the request is about; not necessarily the requester -->
[A] Who is the request about?

## access_request.form_contact_label
<!-- UNMAPPED — how to reach the requester; the reply never goes through this app -->
[A] How should we reach you?

## access_request.form_details_label
<!-- UNMAPPED — optional free text -->
[A] Anything else we should know? (optional)

## access_request.form_submit
<!-- UNMAPPED — the submit control -->
[A] Send this request

## capture.prompt_bill
<!-- UNMAPPED — camera capture (N1 / checklist C1+C5) has no counterpart in his v1, so these five
     ship as engineering text like the other UNMAPPED keys and are listed for him. NOT seeded
     [PLACEHOLDER-eng]: that prefix is the staging/prod boot BLOCK, and holding a deploy over the
     word "Retake" is not what it's for. His round-2 prototype says "Point your camera at the
     bill" + "I'll frame the edges for you and check it's readable" — the second half is NOT
     authorable as written: we detect no document edges and make no readability claim (the B2
     honesty rule), so it would promise two capabilities that don't exist. -->
[A] Point your camera at the bill — get all four corners in the frame.

## capture.prompt_card
<!-- UNMAPPED — the same surface on the insurance-card flow. His prototype: "Snap the front of
     your card" / "Lay it flat — I'll read the member ID and group number." -->
[A] Lay the card flat and fill the frame with it.

## capture.looks_good
<!-- UNMAPPED — the CONFIRM button on the review state. Deliberately the USER's judgement, not
     ours: the prototype's green "Looks readable" badge is a claim we can't check, so the user
     accepts the photo rather than being told it's fine. -->
[A] Use this photo

## capture.retake
<!-- UNMAPPED — the retake button on the review state (checklist C5). -->
[A] Retake

## capture.add_page
<!-- UNMAPPED — the shutter label once page 1 is kept; multi-page bills are the common case. -->
[A] Take the next page

## call_script_opener_payer
<!-- UNMAPPED — his §9 authors the plan/framing, not the four per-call script steps -->
[A] When you reach {party}, give your name and member ID and say you're calling about a billing error you'd like corrected.

## call_script_opener_provider
<!-- UNMAPPED — see call_script_opener_payer -->
[A] When you reach {party}, give your name and account number and say you're calling about a charge you'd like corrected.

## call_script_get_it_in_writing
<!-- UNMAPPED — see call_script_opener_payer -->
[A] Before you hang up, ask them to email or mail you written confirmation of what they agreed to, plus a reference number for the call.

## call_script_if_they_push_back
<!-- UNMAPPED — his §9.5 authors the pushback ROUTE (call_mode.pushback); this is the in-call line -->
[A] If they push back, stay calm and ask them to point you to the specific policy or code that justifies the charge — and if they can't, ask for a supervisor or how to start an appeal.

## call_mode_intro
<!-- UNMAPPED — no §9 counterpart -->
[A] One call at a time. I'll walk you through exactly what to say — tap Next when you're ready for each step.

## call_mode_outro
<!-- UNMAPPED — no §9 counterpart -->
[A] That's the call. When you hear back, tell me what they said and I'll take it from there.

## reveal.gap_callout
<!-- CHECKLIST-E3 — conformance checklist §E item E3 gives this exact framing; his script §6
     has no gap-callout string (§7.1's "{gap} of this shouldn't be yours to pay" is the UNLOCK).
     Sourced to the checklist, not invented. Suppressed entirely when the gap is zero — there is
     no zero-gap variant, and "$0.00 less" would be worse than silence. -->
[A] **{gap}** less than your insurer's number

## finding_no_source
<!-- ENG — the honest no-source state for a finding whose source can't be resolved. Grounding
     doctrine: a claim renders WITH its source or says plainly that it can't yet. -->
[A] I can't point to a source for this one yet — I've flagged it rather than state it as fact.

## freeform_opener
<!-- UNMAPPED — the freeform "Ask Tyndale" scripted opener (Brock's 2026-08-22 field test,
     item 4). Client-rendered as the first assistant bubble of an EMPTY conversation (no LLM
     call, nothing persisted until the user replies). INTERIM engineering seed in Brock's own
     words from the feedback; PROPOSED for his approval in 33_orchestration_script_v2_DRAFT.md —
     shippable copy, deliberately NOT a [PLACEHOLDER-eng] (that would block staging). -->
[A] "What can I help you with today?"

## freeform_opener_chips
<!-- UNMAPPED — the four tappable choices under freeform_opener (item 4). ONE string, chips
     separated by " · "; the client splits on that separator. Each chip is sent verbatim as the
     user's first message. Same interim/PROPOSED status as freeform_opener. -->
[A] "Understand a bill · Check if a bill is correct · Think I'm overcharged · Something else"
