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

## Variables (interpolated by the renderer)
- `{{doc_types}}` — comma-joined classified document types received (acknowledgment).
- `{{delta_dollars}}` — billed-minus-computed savings, formatted e.g. `1,240.00` (three_number_reveal).
- `{{label}}` / `{{how_to_get}}` — a needs_documents checklist item's label + how-to-get text.
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
