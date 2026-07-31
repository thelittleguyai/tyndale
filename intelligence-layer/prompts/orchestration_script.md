---
name: orchestration_script
description: |
  Versioned registry of every system-authored string the chat-first audit thread renders
  (Brock 2026-07-10, DL-91). The runtime renders these values VERBATIM — engineering never
  copy-edits them. Authoring is Brock's side; engineering owns only the loader + this key
  registry + the placeholder guard.
version: 0.1.0
---

# Orchestration script — chat-first audit thread (Phase A)

Each `## <key>` below maps to one thread string. Values here are engineering **placeholders**
(prefixed `[PLACEHOLDER-eng]`) so dev renders something; `assert_production_safety` FAILS a
staging/production boot while any active value still carries that prefix (D1). Brock's authors
replace each body with the real copy — keep the `{{variable}}` slots.

## Voice-tier tags (parsed by the loader — govern rendering, never shown to users)
Each value body MAY lead with `[A]`, `[B]`, or `[C]` (untagged = `[A]`):
- `[A]` fact copy — renders plainly.
- `[B]` legal/coverage claim — the renderer REQUIRES a citation payload; without one it
  renders the graceful-degradation variant instead (`<key>_degraded` if authored, else
  `generic_degraded`) and counts a doctrine_violation. Author a `_degraded` sibling for
  every `[B]` key.
- `[C]` strategy — never predicts an outcome; the loader REFUSES to boot a `[C]` value
  carrying a `{{win_probability}}`-style slot. Tags are stripped before rendering and
  before the placeholder guard (`[B] [PLACEHOLDER-eng] …` still fails staging).

## Variables (interpolated by the renderer)
- `{{doc_types}}` — comma-joined classified document types received (acknowledgment).
- `{{delta_dollars}}` — billed-minus-computed savings, formatted e.g. `1,240.00` (three_number_reveal).
- `{{label}}` / `{{how_to_get}}` — a needs_documents checklist item's label + how-to-get text.
- `{{party}}` — plain-language who-to-call for a gameplan call, e.g. `your insurance company`
  (call_script_opener_payer / call_script_opener_provider).
- `{{filenames}}` — the uploaded file name(s), quoted and comma-joined (wrongdoc.*).
- `{{patient_name}}` — the patient name AS EXTRACTED from the documents (attest.intro).
- `{{total}}` / `{{breakdown}}` — open-case count + comma-joined count breakdown, e.g.
  `2 need documents, 1 with results ready` (record_welcome_summary_fallback).
Unknown `{{slots}}` are left as-is; a missing key renders `<MISSING-script: key>`.

## acknowledgment
[PLACEHOLDER-eng] Got your documents — I can see a {{doc_types}}. Let me take a look.

## stage_label_extraction
[PLACEHOLDER-eng] Reading your documents

## stage_label_translate
[PLACEHOLDER-eng] Sorting out what you were charged for

## stage_label_encounter
[PLACEHOLDER-eng] Confirming what happened

## stage_label_audit
[PLACEHOLDER-eng] Checking every charge against the rules

## verification_intro
[PLACEHOLDER-eng] Quick check — does each of these match what actually happened at your visit? Tap the answer for each.

## verification_nudge
[PLACEHOLDER-eng] Tap one of the buttons on a card above to answer — that's all I need here.

## audit_start
[PLACEHOLDER-eng] Thanks. I'm running the full audit now — I'll compute what you should owe and check it against the bill and your insurer.

## long_wait
[PLACEHOLDER-eng] Still working — a careful audit can take a couple of minutes. I'll have your numbers shortly.

## cap_collision
[PLACEHOLDER-eng] I need a short breather before I can keep going on this — give me a few minutes and I'll pick right back up where I left off.

## needs_documents_intro
[PLACEHOLDER-eng] Here's what I found so far. To finish and lock in your numbers, I need a couple more documents:

## needs_documents_item
[PLACEHOLDER-eng] {{label}} — {{how_to_get}}

## reaudit_announce
[PLACEHOLDER-eng] Got it — that's everything I needed. Re-running your audit now.

## three_number_reveal
[PLACEHOLDER-eng] Here are your three numbers. You may not owe about ${{delta_dollars}} of what you were billed.

## system_error
[PLACEHOLDER-eng] Something went wrong on our end while finishing this audit — our team has been notified and will take a look. You don't need to do anything.

## completion
[PLACEHOLDER-eng] Your audit is complete. Everything I found is below — tap any finding for the details and what to do next.

## verification_map_confirm
[PLACEHOLDER-eng] I've marked {{summary}} — tap to confirm, or fix any I got wrong.

## verification_map_fallback
[PLACEHOLDER-eng] I couldn't tell which charge you meant — tap the answer on each card above and I'll take it from there.

## verification_map_partial_fallback
[PLACEHOLDER-eng] I caught part of that but want to be sure I don't guess — please tap the answer on each card above.

## record_first_upload_frame
[PLACEHOLDER-eng] This is the start of your file. I'll remember your plan and watch what happens next — every bill you send becomes part of your record.

## record_post_audit_keep_doing
[PLACEHOLDER-eng] Here's what I keep doing for you from here: watching your deadlines, re-checking the moment you add a document, and adding this to your growing record so nothing slips.

## call_script_opener_payer
[PLACEHOLDER-eng] When you reach {{party}}, give your name and member ID and say you're calling about a billing error you'd like corrected.

## call_script_opener_provider
[PLACEHOLDER-eng] When you reach {{party}}, give your name and account number and say you're calling about a charge you'd like corrected.

## call_script_get_it_in_writing
[PLACEHOLDER-eng] Before you hang up, ask them to email or mail you written confirmation of what they agreed to, plus a reference number for the call.

## call_script_if_they_push_back
[PLACEHOLDER-eng] If they push back, stay calm and ask them to point you to the specific policy or code that justifies the charge — and if they can't, ask for a supervisor or how to start an appeal.

## call_mode_intro
[PLACEHOLDER-eng] One call at a time. I'll walk you through exactly what to say — tap Next when you're ready for each step.

## call_mode_outro
[PLACEHOLDER-eng] That's the call. When you hear back, tell me what they said and I'll take it from there.

## record_welcome_summary_instructions
[PLACEHOLDER-eng] You write the dashboard's one-line status summary. HARD RULES: state only facts derivable from the case states given; never mention a person, reviewer, team, agent, specialist, or any human/process step; never promise who does what next or when; never say anyone is "processing", "reviewing", or will "pick things up". Frame anything the USER can do plainly (e.g. "re-upload clearer copies"). At most two short sentences, plain text, no medical/legal/financial advice.

## record_welcome_summary_fallback
[PLACEHOLDER-eng] You have {{total}} open cases — {{breakdown}}.

## generic_degraded
[PLACEHOLDER-eng] I can't show you the exact rule text behind this yet — I've flagged it and I'll follow up with the citation.

## attest.intro
[PLACEHOLDER-eng] Before I go further — the name on these documents ({{patient_name}}) isn't the name on your account. So I can keep good records, tell me who this person is to you.

## attest.menu_self
[PLACEHOLDER-eng] This is me — the name is just different on the paperwork

## attest.menu_spouse_partner
[PLACEHOLDER-eng] My spouse or partner

## attest.menu_my_child
[PLACEHOLDER-eng] My child

## attest.menu_parent_relative
[PLACEHOLDER-eng] A parent or relative I help with their care

## attest.menu_other_authorized
[PLACEHOLDER-eng] Someone else I'm authorized to act for

## attest.confirm
[PLACEHOLDER-eng] Thank you — I've noted that. Let's keep going with the review.

## attest.decline_ack
[PLACEHOLDER-eng] Understood — I've closed this one out and I won't review these documents. If that changes, or if the bill turns out to be yours after all, you can start again any time.

## attest.edge_teen
[PLACEHOLDER-eng] One thing worth knowing: for a teenager, some care is private to them by law even from a parent, so parts of a bill may be limited in what they show.

## attest.edge_deceased
[PLACEHOLDER-eng] I'm sorry for your loss. Bills for someone who has died are usually handled through their estate, and the rules about who can act are different — that's worth knowing before you call anyone.

## attest.edge_substance
[PLACEHOLDER-eng] Heads up: care from a substance-use program carries extra federal privacy protection, so what a provider or plan will discuss — even with family — can be narrower than usual.

## wrongdoc.card
[PLACEHOLDER-eng] That's your insurance card — useful, and I've kept it. On its own though there's nothing to check: a card shows your coverage, not what you were charged. Send me the bill or the EOB for the visit and I'll take it from there.

## wrongdoc.sbc
[PLACEHOLDER-eng] That's your plan summary — genuinely useful, and I've attached it to your coverage. It tells me your deductible, coinsurance and out-of-pocket max, which is exactly what I need to work out what you SHOULD owe. Now send me a bill or an EOB and I can check one against the other.

## wrongdoc.clinical
[PLACEHOLDER-eng] {{filenames}} looks like a medical record rather than a bill. I'm not able to audit clinical notes — what I can check is what you were charged: an itemized bill, an Explanation of Benefits, or a statement from the provider.

## wrongdoc.unknown
[PLACEHOLDER-eng] I couldn't tell what {{filenames}} is, so I don't want to guess at it. If you have an itemized bill, an Explanation of Benefits, or a statement from the provider, send that over and I'll check it properly.
