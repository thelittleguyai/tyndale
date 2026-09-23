---
name: orchestration_script
description: |
  Versioned registry of every system-authored string the chat-first audit thread renders
  (Brock 2026-07-10, DL-91). The runtime renders these values VERBATIM — engineering never
  copy-edits them. Authoring is Brock's side; engineering owns only the loader + this key
  registry + the source mapping.
version: 1.1.0
source: docs/build-kit/33_orchestration_script.md (v1.1, 2026-08-18 — §8.4–8.5 unlock-more added, §10.5 amended per Brock's response)
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

## decline.guarantee_trio_no_rate
<!-- UNMAPPED — §10.2-alt, the LAUNCH-DEFAULT path while no citable {base_rate} exists
     (audit 2026-08-27 group 4). SEEDED from the v2 draft's own proposed words (Brock's
     trio scaffolding, minus the rate claim + an honest no-number line); PROPOSED for his
     approval there. The caller picks this variant whenever base_rate is unavailable. -->
[C] "I won't promise you'll win — nobody honest can, and I won't guess with your money. I also won't quote odds I don't have: there isn't yet an honest number for cases exactly like yours, and I'd rather tell you that than invent one. What I can tell you: your case rests on **{strength_of_basis}**, and the best next step is **{next_step}**."

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
<!-- §12.1 — [B] per Brock 2026-08-18 B5: {program_source} IS the citation; absent → the
     degradation variant, never a sourceless program claim. -->
[B] "Honestly, the strongest move here isn't with me — it's **{program_name}**, which exists exactly for this ({program_source}). Here's how to reach them and what to ask. I'll keep your case open on my side so nothing slips while you do."

## handoff.pace
<!-- §12.1 — BORROWED: his script authors one program-handoff string; PACE is the named instance
     ({program_name} = PACE). Brock: author PACE-specific copy if you want it distinct. -->
[B] "Honestly, the strongest move here isn't with me — it's **{program_name}**, which exists exactly for this ({program_source}). Here's how to reach them and what to ask. I'll keep your case open on my side so nothing slips while you do."

## §E · Engineering-owned keys (NOT Brock's voice)

These are rendering mechanism, not product voice: an LLM instruction and the `[B]`-without-
citation fallback. They are engineering-authored by design and are excluded from the
drift guard (nothing in his file to compare against).

## generic_degraded
<!-- ENG — the [B]-without-citation fallback required by his §0 rule 3 -->
[A] I can't show you the exact rule text behind this yet — I've flagged it and I'll follow up with the citation.

## retrieval.unavailable_notice
<!-- UNMAPPED — e2e 2026-09-23 B1; PROPOSED interim seed (engineering). Rendered ONCE in the thread when the audit ran with the rules corpus unreachable (retrieval_unavailable on the case) — never silently. -->
[A] I couldn't reach my rulebook while I checked this bill, so I stuck to what your documents show and to the math. Anything that would need a rule behind it is marked as worth checking — not stated as a fact.

## call_mode.number_on_card
<!-- UNMAPPED — e2e 2026-09-23 M2; PROPOSED interim seed (engineering). Shown in call mode for a payer call when the documents carried no phone number (B4 identifiers) — never a looked-up number. -->
[A] Use the number on the back of your insurance card.

## call_mode.number_on_bill
<!-- UNMAPPED — e2e 2026-09-23 M2; PROPOSED interim seed (engineering). The provider-call twin: no number extracted → point at the bill. -->
[A] Use the phone number printed on your bill.

## finding.pending_input
<!-- UNMAPPED — e2e 2026-09-23 minor; PROPOSED interim seed (engineering). Stands in for an analyst-speak sentence ("omitted from primary finding until confirmed") when nothing user-facing is left of it. -->
[A] I need one more thing to firm this up. It's on your checklist.

## app.not_found_title
<!-- UNMAPPED — e2e 2026-09-23 minor; PROPOSED interim seed (engineering). Replaces Expo's default "Unmatched Route" page. Rendered before any sign-in, via the `app` copy surface. -->
[A] That page isn't here.

## app.not_found_body
<!-- UNMAPPED — e2e 2026-09-23 minor; PROPOSED interim seed (engineering). -->
[A] The link may be old, or the address has a typo. Your bills and your record are one tap away.

## app.not_found_cta
<!-- UNMAPPED — e2e 2026-09-23 minor; PROPOSED interim seed (engineering). -->
[A] Go to my home screen

## finding.no_dollar_change
<!-- UNMAPPED — e2e 2026-09-23 M1; PROPOSED interim seed (engineering). The amount line on a finding card whose finding carries no dollar gap — a real error still worth fixing. -->
[A] No dollar change — still worth fixing.

## gameplan.moment_headline
<!-- UNMAPPED — e2e 2026-09-23 M1; PROPOSED interim seed (engineering). The "Your game plan" moment in the thread, after the finding cards — the one link from the thread to the results page. -->
[A] Your game plan is ready.

## gameplan.moment_cta
<!-- UNMAPPED — e2e 2026-09-23 M1; PROPOSED interim seed (engineering). The button on that moment. -->
[A] See your game plan

## grounding.dropped_notice
<!-- UNMAPPED — e2e 2026-09-23 B2; PROPOSED interim seed (engineering). Rendered ONCE in the thread when a fabrication guard removed a finding (a grounding drop). A guard drop is NOT a photo problem: the §5.1 "too blurry" line is reserved for genuine OCR-quality signals. -->
[A] I saw one more thing, but I could not tie it back to your papers. So I left it out. I don't guess.

## degraded.missing_input
<!-- ENG — e2e 2026-09-23 B2. The fallback for a string whose variable has no value (his §0 rule 2 says "the §5 degradation variant"; §5.1's "too blurry… a clearer photo fixes it" was being substituted for EVERY missing variable, which misattributes a data gap to the user's photo). Neutral, no cause claimed. Brock: your wording. -->
[A] I don't have what I need to say that part yet. So I left it out. I don't guess.

## finding.worth_checking
<!-- UNMAPPED — e2e 2026-09-23 B1; PROPOSED interim seed (engineering). The [C]-style note on a finding whose legal claim had no retrieved source: the observation stays, the claim does not. -->
[A] Worth checking: there may be a rule behind this, but I couldn't confirm it from a source I could read. Ask about it — don't count on it.

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

## explainer_eob
<!-- UNMAPPED — checklist "What is this?" explainers (Brock image-3 item 3, 2026-08-22).
     INTERIM engineering seed; PROPOSED for Brock in 33_orchestration_script_v2_DRAFT.md.
     Pattern per his ask: what the thing is, where to find it, one concrete example. -->
[A] "An Explanation of Benefits is the statement your insurer sends after processing a claim — it's not a bill. It shows what the provider charged, what your plan allowed and paid, and what it says you owe. Find it in your insurance portal under Claims, usually a week or two after the visit."

## explainer_itemized_bill
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. -->
[A] "An itemized bill lists every individual charge with its procedure (CPT) code — not just a total. Providers are required to give you one when you ask. For example: instead of one line saying 'Hospital services — $1,200', it shows each test and service on its own line."

## explainer_sbc
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. -->
[A] "The Summary of Benefits and Coverage is the standard document that describes what your plan covers — your deductible, out-of-pocket max, and copays. Every plan is required to publish one. Find it in your insurance portal under Plan Documents, or ask your HR team or insurer."

## explainer_deductible
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. The dollar figure is a GENERIC
     illustrative example (his one-concrete-example pattern), never a user-specific number. -->
[A] "Your deductible is the amount you pay out of pocket each plan year before your plan starts sharing costs. It's on your SBC, and usually on your insurance portal's summary page. For example: with a $2,000 deductible, you pay the first $2,000 of allowed charges each year."

## explainer_deductible_met
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. Generic educational form only —
     no invented user-specific numbers (tier-1 style rule). -->
[A] "This is how much of your deductible you had already paid this plan year before this visit. Your insurance portal shows it as a running total — often labeled 'deductible met' or 'year to date'. This one usually moves your number the most: every dollar already met comes off what you can be asked to pay first."

## explainer_oop_max
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. -->
[A] "Your out-of-pocket maximum is the most you can be required to pay for covered care in a plan year — once you reach it, your plan pays 100% of covered charges. It's listed on your SBC right next to the deductible."

## explainer_oop_met
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. -->
[A] "This is how much you had already paid toward your out-of-pocket maximum this plan year before this visit. Your portal shows it as a running total. If you're close to the max, that caps what this visit can cost you."

## explainer_visit_confirm
<!-- UNMAPPED — same interim/PROPOSED status as explainer_eob. -->
[A] "Confirming what the visit was for helps me check the charges against what actually happened. Tap the option that matches, or describe it in your own words — plain language is fine; you don't need medical terms."

## checklist_item_ack
<!-- UNMAPPED — one-line checklist completion acknowledgment (Brock image-3 item 4,
     2026-08-22): the conversation reflects checklist progress. Deliberately no fanfare.
     Same interim/PROPOSED status as the explainer keys. -->
[A] "Got it — {item_label} saved."

## home.banner_title
<!-- UNMAPPED — homescreen welcome banner (Brock mockups 2026-08-22, honest subset).
     INTERIM engineering seed; PROPOSED in 33_orchestration_script_v2_DRAFT.md.
     HONESTY CONSTRAINT for any rewrite: the subline keys below may only describe REAL,
     computed case state. Proactive-monitoring claims ("deadlines watched", "numbers
     re-checked") are B8 — NOT BUILT — and are test-banned until that machinery exists. -->
[A] "Welcome back, {name}."

## home.banner_subline_empty
<!-- UNMAPPED — zero open cases. Same interim/PROPOSED status + honesty constraint. -->
[A] "Ready when you are — check a bill and I'll take it from there."

## home.banner_subline_active
<!-- UNMAPPED — open cases, some need the user. {cases_phrase} e.g. "2 open cases";
     {needs_phrase} e.g. "1 needs something from you". Computed, always true. -->
[A] "{cases_phrase} — {needs_phrase}."

## home.banner_subline_quiet
<!-- UNMAPPED — open cases, none blocked on the user. Same status + constraint. -->
[A] "{cases_phrase} — nothing needs you right now."

## checkin.fixing_it
<!-- UNMAPPED — dashboard check-in chips (Brock mockups 2026-08-22 item 5). These three are
     CALL ROUTES, not outcomes ("they said they'd fix it" is a claim by the party we audit) —
     a tap defers the real outcome question by the follow-up window, per the H6 doctrine.
     INTERIM engineering seeds in Brock's own mockup words; PROPOSED in the v2 draft. -->
[A] "They're fixing it"

## checkin.pushed_back
<!-- UNMAPPED — same status as checkin.fixing_it. -->
[A] "They pushed back"

## checkin.left_message
<!-- UNMAPPED — same status as checkin.fixing_it. -->
[A] "I left a message"

## explainer_coinsurance
<!-- UNMAPPED — checklist explainer for the coinsurance item (audit 2026-08-27 item 4).
     Same interim/PROPOSED status and what/where/example pattern as the other explainers. -->
[A] "Coinsurance is the percentage of each covered charge you pay after your deductible is met — your plan pays the rest. It's on your SBC next to the deductible. For example: with 20% coinsurance, a $100 allowed charge costs you $20 once the deductible is met."

## dashboard.headline_unreadable
<!-- UNMAPPED — open-case card headline, unreadable documents (audit 2026-08-27 item 6:
     was hardcoded in the dashboard route). INTERIM engineering seed, PROPOSED in the v2
     draft; same words as shipped, now drift-guarded like everything else. -->
[A] "We couldn't read your documents — try re-uploading a clearer copy"

## dashboard.headline_finding
<!-- UNMAPPED — open-case card headline when the latest finding names the case.
     {category_label} e.g. "Cost sharing miscalculation"; {finding_type_label} e.g.
     "payer-side". Same interim/PROPOSED status. -->
[A] "{category_label} ({finding_type_label})"

## dashboard.headline_uploaded
<!-- UNMAPPED — open-case card headline pre-audit. {doc_type} is the classified document
     type. Same interim/PROPOSED status. -->
[A] "Uploaded {doc_type} — audit pending"

## dashboard.headline_open
<!-- UNMAPPED — open-case card headline with no documents yet. Same status. -->
[A] "Case open — awaiting documents"

## §G · Guided intake (doc 40) — PROPOSED interim seeds

Every string the guided `/intake` route renders (doc 40 §A2/§A6/§C10/§C12). **None of this is
Brock's authored copy yet.** Each value is a shippable INTERIM seed — taken from the packet's
own lines where it gives one (rewritten to grade 5 where needed), from the CO-1A wizard's
strings otherwise — marked UNMAPPED and PROPOSED for his authoring pass in
`docs/build-kit/33_orchestration_script_v2_DRAFT.md` ("Guided intake"). Excluded from the drift
guard (nothing to compare against) and INCLUDED in the grade-5 guard
(`tests/test_intake_reading_level.py`): every `intake.*` value must score ≤ 5.9 Flesch–Kincaid,
and a glossed term (deductible, coinsurance, EOB, out-of-pocket, SBC, MSN, itemized) may appear
only on a screen that carries its `gloss_<term>` key. Key shape: `intake.<screen>.<slot>`.
Reused, NOT duplicated here: `upload_trust_microcopy` (§1.2), `dataquality_summary_not_itemized`
(§5.2), `wrongdoc.*` (§5.3), `attest.*` (§3), `system_error*` / `cap_collision` (§10).


## — intake.chrome · on every guided screen

## intake.chrome.save_exit
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Save and exit

## intake.chrome.saved
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C7 line -->
[A] Saved. You can stop now and come back later.

## intake.chrome.see_example
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] See an example

## intake.chrome.help_find
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A5 line -->
[A] Help me find it

## intake.chrome.email_steps
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A5 line -->
[A] Email me these steps

## intake.chrome.email_sent
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Sent. Check your email.

## intake.chrome.email_failed
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I could not send that email. The steps are still here on this page.

## intake.chrome.continue
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Continue

## intake.chrome.back
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Back

## intake.chrome.close
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Close

## intake.chrome.open_sample
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Open the sample

## intake.chrome.load_error
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] I could not load this step. Your work is saved. Please try again.

## intake.chrome.save_error
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] I could not save that. Check your connection and try again.

## intake.chrome.retry
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Try again


## — intake.progress · the progress bar (§A8)

## intake.progress.started
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] {filled} of {total} — nice start

## intake.progress.going
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] {filled} of {total} done

## intake.progress.all
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] All {total} done

## intake.progress.kept_note
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] I moved one of your papers to a new group. Your progress stays the same.

## intake.progress.label_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] Bill

## intake.progress.label_card
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] Card

## intake.progress.label_plan_rules
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] Plan rules

## intake.progress.label_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] EOB

## intake.progress.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.progress.label_timeline
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] Timeline

## intake.progress.label_about_you
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] About you

## intake.progress.label_confirmations
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A8 line -->
[A] Quick checks


## — intake.resume · save and resume (§C7)

## intake.resume.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C7 line -->
[A] Pick up where you left off.

## intake.resume.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your work is saved. Next up: {group_label}.

## intake.resume.home_body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (the home screen's resume card — it cannot name the next group without a planner call) -->
[A] Your bill check is saved. A few more steps and I can run it.

## intake.resume.case_label
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (the status chip on a case still on the guided route — home Open Cases card and Record rows) -->
[A] Not finished yet

## intake.resume.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Keep going

## intake.resume.new
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Start a new bill

## intake.resume.link_expiry
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C7 line -->
[A] To come back, ask for a new sign-in link. Each link works for {minutes} minutes.


## — intake.welcome · #1 landing

## intake.welcome.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Let's check your bill.

## intake.welcome.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I will ask for a few papers, one at a time. I read them for you, so there is little to type.

## intake.welcome.doctrine
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B1 line -->
[A] I do not assume the bill is right. I do not assume your insurer is right. I check both.

## intake.welcome.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Start with my bill


## — intake.handoff · exit — a population Phase 1 does not carry

## intake.handoff.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Let's finish this in chat.

## intake.handoff.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] This step-by-step path is built for job and self-bought plans so far. For {population_label}, I check your bill in our chat. Nothing you added is lost.

## intake.handoff.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Go to chat

## intake.handoff.label_medicare
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Medicare

## intake.handoff.label_medicare_advantage
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] a Medicare plan

## intake.handoff.label_medicaid
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Medicaid

## intake.handoff.label_dual
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Medicare with Medicaid

## intake.handoff.label_self_pay
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] a bill with no insurance

## intake.handoff.label_tricare_va
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] TRICARE or VA coverage

## intake.handoff.label_other
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] your kind of plan


## — intake.bill · #2–3 the bill

## intake.bill.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B2 line -->
[A] Take a photo of your bill.

## intake.bill.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The itemized bill works best. A photo or a file both work.

## intake.bill.gloss_itemized
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Itemized means each charge is on its own line, with a short code next to it.

## intake.bill.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add my bill

## intake.bill.no_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B2 line -->
[A] I don't have the bill

## intake.bill.no_bill_note
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B2 line -->
[A] That's okay. We can start with your Explanation of Benefits (EOB).

## intake.bill.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line (the bill screen names the EOB in its no-bill note) -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.


## — intake.bill_itemized · #3 summary-bill coaching (body = §5.2's dataquality_summary_not_itemized, reused)

## intake.bill_itemized.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C5 line -->
[A] This bill is a summary.

## intake.bill_itemized.gloss_itemized
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Itemized means each charge is on its own line, with a short code next to it.

## intake.bill_itemized.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add the itemized bill

## intake.bill_itemized.secondary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Keep going with this bill

## intake.bill_itemized.secondary_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I can still check the totals. I can't check each charge.


## — intake.bill_summary · #5 read-back + other bills for this visit (§C1)

## intake.bill_summary.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B5 line -->
[A] Here is what I read.

## intake.bill_summary.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Take a look. If something is wrong, add a clearer photo.

## intake.bill_summary.row_provider
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] From

## intake.bill_summary.row_date
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Date of visit

## intake.bill_summary.row_patient
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Name on the bill

## intake.bill_summary.row_account
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Account number

## intake.bill_summary.row_missing
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I could not read this

## intake.bill_summary.other_bills
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B5 line -->
[A] Did you get other bills for this same visit?

## intake.bill_summary.other_bills_why
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C1 line -->
[A] One hospital visit can bring many bills. The doctor, the lab and the hospital may each send one. I check them as one.

## intake.bill_summary.yes
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Yes, add another bill

## intake.bill_summary.no
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No, that's all

## intake.bill_summary.fix
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Something is off


## — intake.eob · #6 EOB

## intake.eob.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] Now your Explanation of Benefits (EOB).

## intake.eob.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.eob.other_name
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] It may have a different name on your insurer's website.

## intake.eob.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] It shows what your insurer paid and what it says you owe. I check that math too.

## intake.eob.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add my EOB

## intake.eob.skip
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B6 line -->
[A] I don't have it

## intake.eob.skip_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B6 line -->
[A] I can still check the hospital's charges. But I can't check your insurer's math. That is where the bigger mistakes often are.


## — intake.card · #7 card

## intake.card.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B7 line -->
[A] Next, your insurance card.

## intake.card.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Take a photo of the front and the back. It tells me which plan you have.

## intake.card.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add my card

## intake.card.skip
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B7 line -->
[A] I don't have my card

## intake.card.skip_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B7 line -->
[A] That's okay. It may be on your bill. If not, I will ask you to type your insurer's name.


## — intake.insurer · which insurer — only when no document named it

## intake.insurer.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Who is your insurer?

## intake.insurer.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I could not find it on your papers. Type it the way it looks on a letter from them.

## intake.insurer.body_suggested
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (shown INSTEAD of body when the card gave a low-confidence read — the fields arrive pre-filled) -->
[A] This is what I read on your card. Fix anything that is wrong, then save.

## intake.insurer.field_payer
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Insurer name

## intake.insurer.field_member_id
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Member ID, if you have it

## intake.insurer.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Save

## intake.insurer.skip
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Skip for now

## intake.insurer.skip_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (a way out always says what it costs) -->
[A] Without it, I can't look up your plan. I may need to ask you more.


## — intake.coverage_type · kind of coverage — only when detection could not tell

## intake.coverage_type.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] How do you get your health insurance?

## intake.coverage_type.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] This tells me which rules apply to your bill.

## intake.coverage_type.opt_job_or_bought
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Through a job, or I bought it myself

## intake.coverage_type.opt_medicare
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Medicare

## intake.coverage_type.opt_medicaid
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Medicaid

## intake.coverage_type.opt_military_va
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] TRICARE or VA

## intake.coverage_type.opt_none
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] I don't have insurance

## intake.coverage_type.opt_not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I'm not sure

## intake.coverage_type.not_sure_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (a way out always says what it costs) -->
[A] That's fine. I'll use the rules most plans follow, and I'll say so.


## — intake.plan_rules · #8 plan rules (SBC)

## intake.plan_rules.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] Now your plan's rulebook.

## intake.plan_rules.gloss_sbc
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook.

## intake.plan_rules.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] It is a few pages long. Your insurer's website has it. So does the benefits office at your job.

## intake.plan_rules.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add my SBC

## intake.plan_rules.skip
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C9 line -->
[A] I can't find it

## intake.plan_rules.skip_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B8 line -->
[A] Without it, I will show your share as a range, not one number.


## — intake.plan_rules_confirm · #8 Plan Library variant — confirm this matches

## intake.plan_rules_confirm.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B8 line -->
[A] I may already have your plan's rules.

## intake.plan_rules_confirm.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B8 line -->
[A] I have these on file for {payer}. Do they match your plan?

## intake.plan_rules_confirm.gloss_sbc
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook.

## intake.plan_rules_confirm.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.plan_rules_confirm.gloss_out_of_pocket
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The out-of-pocket limit is the most you pay in one plan year.

## intake.plan_rules_confirm.gloss_coinsurance
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Coinsurance is your share of the cost after the deductible.

## intake.plan_rules_confirm.row_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Deductible

## intake.plan_rules_confirm.row_oop
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Out-of-pocket limit

## intake.plan_rules_confirm.row_coinsurance
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Coinsurance

## intake.plan_rules_confirm.yes
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Yes, these match

## intake.plan_rules_confirm.no
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] No, something is off


## — intake.plan_year · #10 plan year

## intake.plan_year.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B10 line -->
[A] When does your plan year start?

## intake.plan_year.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Many plans start in January, but not all. Your deductible starts over on that day.

## intake.plan_year.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.plan_year.opt_not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I'm not sure

## intake.plan_year.not_sure_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (a way out always says what it costs) -->
[A] That's fine. I just won't know if a month is missing.


## — intake.timeline · #11–12 the EOB timeline (§A7)

## intake.timeline.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Your EOBs this plan year.

## intake.timeline.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.timeline.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.timeline.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Your deductible adds up over the year. So I need each EOB from the start of your plan year up to this visit.

## intake.timeline.visit_marker
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Your visit

## intake.timeline.after_visit
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] After your visit. It does not change this bill.

## intake.timeline.no_date
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I could not read a date on this one.

## intake.timeline.gap
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] I don't see one for {month}.

## intake.timeline.gap_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Without it, I'll show your share as a range.

## intake.timeline.confirm
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] I count {n} EOBs, {start} to {end}, none for anyone else on your plan. Is that all of them?

## intake.timeline.confirm_one
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] I count one EOB, from {start}, and none for anyone else on your plan. Is that the only one?

## intake.timeline.confirm_family
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] I count {n} EOBs, {start} to {end}, for {members} people on your plan. Is that all of them?

## intake.timeline.confirm_yes
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Yes, that's all

## intake.timeline.confirm_no
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No, there are more

## intake.timeline.add_more
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add another EOB


## — intake.deductible_met · manual deductible ask — only when the EOBs cannot say

## intake.deductible_met.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] How much of your deductible had you paid?

## intake.deductible_met.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.deductible_met.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I mean before this visit, in this plan year. Your insurer's website shows it.

## intake.deductible_met.field_amount
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Amount paid so far

## intake.deductible_met.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Save

## intake.deductible_met.not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I'm not sure

## intake.deductible_met.not_sure_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] We don't know what you'd already paid by then, so we won't guess. I will show your share as a range.


## — intake.oop_met · manual out-of-pocket ask — only when the EOBs cannot say

## intake.oop_met.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] How much counted toward your out-of-pocket limit?

## intake.oop_met.gloss_out_of_pocket
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The out-of-pocket limit is the most you pay in one plan year.

## intake.oop_met.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I mean before this visit, in this plan year. Your insurer's website shows it.

## intake.oop_met.field_amount
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Amount paid so far

## intake.oop_met.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Save

## intake.oop_met.not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I'm not sure

## intake.oop_met.not_sure_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] We don't know what you'd already paid by then, so we won't guess. I will show your share as a range.


## — intake.attest · #13 who was it for → attest-and-proceed (attest.* keys do the talking)

## intake.attest.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B13 line -->
[A] Who is this bill for?

## intake.attest.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed — the button under your §3 confirm line -->
[A] I confirm

## intake.attest.decline
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed — the decline path is always offered (checklist F1) -->
[A] I can't confirm this

## intake.attest.back_home
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Back to home


## — intake.other_insurance · #14 other insurance

## intake.other_insurance.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B14 line -->
[A] Do you have a second health plan?

## intake.other_insurance.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B14 line -->
[A] Some people are on two plans. If you are, I check it. I don't assume it pays the rest.

## intake.other_insurance.yes
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Yes

## intake.other_insurance.no
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No

## intake.other_insurance.not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I'm not sure

## intake.other_insurance.not_sure_consequence
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed (a way out always says what it costs) -->
[A] That's fine. I'll check this bill with the one plan I know.


## — intake.reading · #4 reading it

## intake.reading.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B4 line -->
[A] Reading your bill.

## intake.reading.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] This takes a minute or two. You can leave and come back. Your work is saved.


## — intake.facts_only · #15 facts only

## intake.facts_only.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B15 line -->
[A] A few quick facts about your visit.

## intake.facts_only.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B15 line -->
[A] I only ask what happened. I never ask if the care was right. That is between you and your doctor.

## intake.facts_only.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Okay


## — intake.confirmations · #16 confirmations

## intake.confirmations.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B16 line -->
[A] Did these happen?

## intake.confirmations.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Each one is a charge on your bill, in plain words. Tell me if it happened.

## intake.confirmations.yes
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] Yes

## intake.confirmations.no
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: carried from the CO-1A wizard, rewritten toward grade 5 -->
[A] No

## intake.confirmations.not_sure
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B16 line -->
[A] I'm not sure

## intake.confirmations.not_sure_note
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B16 line -->
[A] That's fine. I will mark it as not settled.

## intake.confirmations.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Done


## — intake.readiness · #17 readiness — the planner's summary

## intake.readiness.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B17 line -->
[A] Here is what I have.

## intake.readiness.body
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B17 line -->
[A] You can run the check now. Or add what is missing first, for a sharper answer.

## intake.readiness.resolved
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Have it

## intake.readiness.unresolved
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Missing

## intake.readiness.skipped
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Skipped

## intake.readiness.edit
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B17 line -->
[A] Change

## intake.readiness.primary
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Check my bill

## intake.readiness.cannot_run
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Add a bill or an insurer statement first. I need one of them to check.

## intake.readiness.item_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your bill

## intake.readiness.item_itemized_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] A bill with each charge listed

## intake.readiness.item_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed. A2 (2026-09-23): the document's printed name, glossed on this screen -->
[A] Your Explanation of Benefits (EOB)

## intake.readiness.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.readiness.item_payer
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your insurer

## intake.readiness.item_plan_rules
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your plan's rulebook

## intake.readiness.item_plan_year_start
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] When your plan year starts

## intake.readiness.item_eob_completeness
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] All your EOBs

## intake.readiness.item_deductible_met
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] What you had paid before this visit

## intake.readiness.item_oop_max_met
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] What counted toward your yearly limit

## intake.readiness.item_coverage_type
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your kind of coverage

## intake.readiness.item_attestation
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Who the bill is for

## intake.readiness.item_other_insurance
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] A second health plan

## intake.readiness.item_encounter_facts
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Facts about your visit


## — intake.limits · what an unresolved item limits (readiness lines)

## intake.limits.no_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No bill yet. I can only check your Explanation of Benefits (EOB).

## intake.limits.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line (limits lines render on the readiness screen) -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.limits.summary_bill
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §C5 line -->
[A] This bill shows totals only. I can't check each charge.

## intake.limits.no_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B6 line -->
[A] No EOB. I can't check your insurer's math.

## intake.limits.no_payer
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I don't know your insurer. Some plan rules can't be checked.

## intake.limits.no_plan_rules
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B8 line -->
[A] No plan rulebook. Your share becomes a range.

## intake.limits.no_plan_year
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] I don't know when your plan year starts. I can't place your visit in the year.

## intake.limits.incomplete_eobs
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A7 line -->
[A] Some EOBs may be missing. Your share becomes a range.

## intake.limits.no_accumulator
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] I don't know what you had paid so far. Your share becomes a range.

## intake.limits.no_coverage_type
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I don't know your kind of coverage. I will use the common rules.

## intake.limits.no_other_insurance
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] I don't know if you have a second plan.

## intake.limits.no_confirmations
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Visit facts are not checked yet. Some charges stay open.


## — intake.analysis · #18 analysis

## intake.analysis.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B18 line -->
[A] Checking your bill.

## intake.analysis.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.analysis.step_read
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Reading your papers

## intake.analysis.step_position
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B18 line -->
[A] Working out where your deductible stood

## intake.analysis.step_provider
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B18 line -->
[A] Checking the bill's side

## intake.analysis.step_payer
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §B18 line -->
[A] Checking your insurer's side

## intake.analysis.leave
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] This can take a few minutes. You can leave. I will keep working.


## — intake.unlock · the unlock moment while billing is dark

## intake.unlock.headline
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: §7.1's unlock.card WITHOUT its price clause — rendered while no one is charged (unlock_gate_mode free_beta / block) -->
[A] {gap} of this should not be yours to pay. Your plan to fix it is ready.

## intake.unlock.proceed
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] See my plan

## intake.unlock.free_beta
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: prompt item 8 -->
[A] Free while we're in beta.

## intake.unlock.blocked
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] This step is not open yet.


## — intake.example · example registry callouts (§A3)

## intake.example.gloss_sbc
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook.

## intake.example.gloss_msn
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An MSN is the Medicare Summary Notice. Medicare mails it to show what it paid.

## intake.example.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.example.gloss_out_of_pocket
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The out-of-pocket limit is the most you pay in one plan year.

## intake.example.source_federal
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] This sample comes from the U.S. government. It is not your plan.

## intake.example.sbc_title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] A sample SBC

## intake.example.sbc_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Top right: the coverage period. The first date is when your plan year starts.

## intake.example.sbc_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] First row: the overall deductible, for one person and for a family.

## intake.example.sbc_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Third row: other deductibles, like one just for drugs.

## intake.example.sbc_4
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Fourth row: the out-of-pocket limit. It lists one number in the network and one out of it.

## intake.example.sbc_5
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Page 2: two columns of costs. One is for network doctors. One is for doctors outside it.

## intake.example.sbc_6
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Last page: three made-up patients. They show how the plan splits a real bill.

## intake.example.msn_title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] A sample MSN

## intake.example.msn_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Top of page 1: the words "This is not a bill."

## intake.example.msn_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Page 1: the box named "Your Deductible Status." It shows how much you have met.

## intake.example.msn_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Page 1: "Total You May Be Billed" for this period.

## intake.example.msn_4
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Page 3: the claims table. The last column is the most the doctor may bill you.

## intake.example.msn_5
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A3 line -->
[A] Last page: how to appeal, and the date you must do it by.


## — intake.help · "Help me find it" — generic fallbacks (§A5)

## intake.help.title
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A5 line -->
[A] Where to find it

## intake.help.generic_note
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A5 line -->
[A] These are general steps. Your insurer's website may use other names.

## intake.help.payer_note
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A5 line -->
[A] These steps are for {payer}.

## intake.help.gloss_eob
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it.

## intake.help.gloss_sbc
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A2 line -->
[A] It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook.

## intake.help.gloss_deductible
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: seeded from the packet §A6 line -->
[A] The deductible is the amount you pay before insurance starts paying.

## intake.help.gloss_out_of_pocket
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The out-of-pocket limit is the most you pay in one plan year.

## intake.help.gloss_itemized
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Itemized means each charge is on its own line, with a short code next to it.

## intake.help.email_subject
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Your steps from Tyndale

## intake.help.email_intro
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Here are the steps you asked for. Come back to Tyndale when you have it.

## intake.help.eob_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Sign in to your insurer's website or app.

## intake.help.eob_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Look for Claims. It may be called Claims and Payments.

## intake.help.eob_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Find the claim with your visit date. Open it.

## intake.help.eob_4
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Look for a link that says EOB, or View Statement. Save it as a file.

## intake.help.eob_5
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No luck? Call the number on the back of your card. Ask them to mail or email the EOB.

## intake.help.sbc_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Sign in to your insurer's website or app.

## intake.help.sbc_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Look for Plan Documents or Benefits.

## intake.help.sbc_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Open the file named Summary of Benefits and Coverage. Save it.

## intake.help.sbc_4
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Got your plan at work? Your benefits office has it too. They must give it to you when you ask.

## intake.help.insurance_card_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Check your wallet, or a drawer with your mail from the insurer.

## intake.help.insurance_card_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No card? Sign in to your insurer's app. Look for ID Card. You can save a copy.

## intake.help.insurance_card_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Still no card? Your bill or EOB may show the insurer and your member ID.

## intake.help.itemized_bill_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Call the billing number on your bill.

## intake.help.itemized_bill_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Ask for the itemized bill, with every charge and its code.

## intake.help.itemized_bill_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Give them your account number and your visit date.

## intake.help.itemized_bill_4
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] They can mail it, email it, or post it on their website. There is no charge.

## intake.help.accumulators_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Sign in to your insurer's website or app.

## intake.help.accumulators_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Look for Deductible, or Plan Balances. It is often on the first page.

## intake.help.accumulators_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Write down the amount you have paid so far, and the date it shows.

## intake.help.plan_year_1
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] Look at the top of your SBC. Find the words Coverage Period.

## intake.help.plan_year_2
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] The first date is the day your plan year starts.

## intake.help.plan_year_3
<!-- UNMAPPED — guided intake (doc 40); PROPOSED interim seed: engineering seed -->
[A] No SBC? Your benefits office or your insurer can tell you the date.

## §L · Landing page — "Not a chatbot with opinions" playback (marketing site, 2026-09-23)

## landing.compare.user_q1
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). The one question BOTH panes of the marketing site's chat-compare playback answer. Illustrative numbers = the hero card's fixture ($2,347.18 billed / $1,184.60 EOB / $612.40 Tyndale); apps/web-marketing/src/content/landing-compare.json mirrors this text and a guard test keeps it verbatim. -->
[A] My hospital billed me $2,347.18 for an MRI. My insurer says I owe $1,184.60. Is that right?

## landing.compare.tyndale_open
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). Tyndale's first turn: reads the documents it has and names the one thing it cannot know yet. -->
[A] Let me read it, not guess. I have your plan's Summary of Benefits and this EOB. The EOB puts $965.25 toward your deductible. Whether that is right depends on what you had already paid this year.

## landing.compare.tyndale_range
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). Follows intake.limits.no_accumulator in the playback: the honest bracket while the accumulator is unknown (20% of the plan rate with the deductible met, up to the EOB's own figure). -->
[A] Right now that is **$412.40 to $1,184.60**. Your other EOBs from this year would pin it down.

## landing.compare.user_eobs
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). The visitor's second turn in the Tyndale pane. -->
[A] I met most of it in February. Here are my other EOBs from this year.

## landing.compare.tyndale_deductible
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). The payer-side finding, every number from a named document; rendered with finding_card_source ("your Feb 3 and Feb 20 EOBs") as its chip. -->
[A] Got them. Your Feb 3 and Feb 20 EOBs put you at **$1,750.00** of your **$2,000.00** deductible before this scan. So only **$250.00** belongs on this one — not $965.25.

## landing.compare.tyndale_plan_rule
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). The coverage line — read from the plan's own Summary of Benefits, rendered with finding_card_source ("your Summary of Benefits — Imaging, 20% after deductible") as its chip. -->
[A] After the deductible, your plan pays 80% of imaging and you pay 20%. 20% of the remaining **$1,812.00** is **$362.40**.

## landing.compare.user_win
<!-- UNMAPPED — landing motion parity Phase A (2026-09-23); PROPOSED interim seed (engineering). The visitor's last turn in both panes; Tyndale answers with decline.guarantee_trio_no_rate. -->
[A] Will I win if I dispute it?
