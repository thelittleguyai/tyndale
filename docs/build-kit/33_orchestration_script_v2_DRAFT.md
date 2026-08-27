# Orchestration Script v2 — DRAFT ADDITIONS for Brock sign-off

**Status: DRAFT — nothing here renders until Brock approves and it ships as v2 of `33_orchestration_script.md`.** The runtime registry cannot be edited directly (CI drift guard). Drafted by Cowork 2026-08-12 in the established v1 voice; **no facts, statistics, citations, or dollar figures invented** — where a variable needs a source of truth that doesn't exist, it's flagged, not filled.

Sections mirror v1 numbering. New keys carry their registry names. `[A]/[B]/[C]` tags per v1 rules.

---

## ~~§3 addition — substance-use-program edge prompt~~ RESOLVED 2026-08-27: ruled OUT

*Your 2026-08-18 response (v1.1 changelog A5) dropped the SUD case — `attest.edge_substance`
was removed from the registry and a test asserts its absence. Kept struck for the record;
this is a CLOSED question, not a re-ask.*

**3.6 Elevated prompt — substance-use treatment program** `[A]` — key: `attest.edge_substance`
> "One thing worth knowing: records from a substance-use treatment program carry extra privacy protection — often even from family. If this bill is from one, {patient_name} may need to be the one to bring it to me. Want to continue, or have them take it from here?"

*Modeled on your teen prompt (§3.3): prompt, not a block; same "want to continue, or…" close. If you'd rather DROP the SUD case, delete this and amend checklist F2 instead — your call, both documents can't stand as-is.*

## §4 additions — verification support strings

**4.5 Typed-instead-of-tapped nudge** `[A]` — key: `verification_nudge`
*Renders today (interim): "Tap one of the buttons on a card above to answer — that's all I need here." — you're replacing shipped words, not filling a blank.*
> "Either way works — tap the buttons, or tell me in your own words and I'll mark the card for you to confirm. The tap is what makes it official."

**4.6 Partial-mapping fallback** `[A]` — key: `verification_map_partial_fallback`
*Renders today (interim): "I caught part of that but want to be sure I don't guess — please tap the answer on each card above."*
> "I've marked the ones I'm sure about. These I don't want to guess on — which did you mean?"

*(Companion to your §4.3 low-confidence fallback; renders when SOME of a typed answer mapped and the rest didn't.)*

## §5 addition — the itemized-request script (the words §5.2 exists to deliver)

**Variable: `{itemized_request_script}`** — authored value, not computed:
> "Hi — I'd like a fully itemized bill for account {account_number}, date of service {service_date}: every service listed line by line, with its billing code and its charge. Mail, email, or the patient portal all work."

## §5.3 per-branch variants (your 3.4 question — OPTION B, if one string isn't enough)

**5.3a Insurance card** `[A]` — key: `wrongdoc.card`
> "That's your insurance card — useful, and I've saved your plan details from it. It's not something I can audit, though. To check a bill I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**."

**5.3b Plan summary / SBC** `[A]` — key: `wrongdoc.sbc`
> "That's your plan's benefits summary — genuinely helpful, and I've noted what it says about your coverage. To audit a charge I still need the **itemized bill** or the **EOB**."

**5.3c Clinical record** `[A]` — key: `wrongdoc.clinical`
> "That looks like a medical record, not a bill — and I don't need your clinical details to check your charges. The **itemized bill** or the **EOB** is what I can work with."

**5.3d Unplaceable** — your v1 §5.3 generic stands unchanged.

*If you prefer ONE string (Option A), say so and all four branches keep rendering §5.3 with `{detected_doc_type}` — no code change either way.*

## §9 additions — the four per-call script beats + call-mode frame

**9.6 Payer call opener** `[A]` — key: `call_script_opener_payer`
> "Hi — I'm calling about claim {claim_number} for {patient_name}, date of service {service_date}. I'd like to walk through how this claim was processed — I have my EOB in front of me."

~~*⚠️ Dependency: `{claim_number}` is not yet extracted/stored (delta B4).*~~ *(struck 2026-08-27: B4 shipped — claim/account numbers are typed per-document fields and the slot resolves.)*
*Renders today (interim): "When you reach {party}, give your name and member ID and say you're calling about a billing error you'd like corrected."*

**9.7 Provider call opener** `[A]` — key: `call_script_opener_provider`
*Renders today (interim): "When you reach {party}, give your name and account number and say you're calling about a charge you'd like corrected."*
> "Hi — I'm calling about account {account_number} for {patient_name}, date of service {service_date}. I have a question about a charge before I pay anything."

**9.8 Get it in writing** `[A]` — key: `call_script_get_it_in_writing`
*Renders today (interim): "Before you hang up, ask them to email or mail you written confirmation of what they agreed to, plus a reference number for the call."*
> "Before we hang up — could you send me that in writing? Email or a portal message is fine. And may I have your name and a reference number for this call?"

**9.9 If they push back** `[C]` — key: `call_script_if_they_push_back`
*Renders today (interim): "If they push back, stay calm and ask them to point you to the specific policy or code that justifies the charge — and if they can't, ask for a supervisor or how to start an appeal."*
> "I understand — and you don't have to take my word for it. Could you mark the account as disputed while it's reviewed? I'll follow up in writing with exactly what I'm seeing."

**9.10 Call-mode intro** `[A]` — key: `call_mode_intro`
*Renders today (interim): "One call at a time. I'll walk you through exactly what to say — tap Next when you're ready for each step."*
> "You've got this. Everything you need is pinned up top — the numbers, and your script. One step at a time; I'm right here."

**9.11 Call-mode outro** `[A]` — key: `call_mode_outro`
*Renders today (interim): "That's the call. When you hear back, tell me what they said and I'll take it from there."*
> "That call's done — nice work. How did it go?"

*(Flows into your §9.4 options.)*

## §10 additions

**10.2-alt Guarantee decline, no cited base rate** `[C]` — key: `decline.guarantee_trio_no_rate` — **the launch-default path — SEEDED 2026-08-27** *(this exact text is LIVE in the registry and the decline caller renders it whenever no citable rate exists — previously the rated string degraded with a doctrine violation on every render; approve or rewrite)*
> "I won't promise you'll win — nobody honest can, and I won't guess with your money. I also won't quote odds I don't have: there isn't yet an honest number for cases exactly like yours, and I'd rather tell you that than invent one. What I can tell you: your case rests on **{strength_of_basis}**, and the best next step is **{next_step}**."

**10.1-continuation Fabrication reframe** `[A]` — key: `decline.fabrication_reframe`
> "The biggest one: {finding_title} — worth **{finding_amount}**, and every word of it checks out. That's the case I'd make."

*(Renders after your §10.1's closing colon; names the strongest verified finding. Confirm this is the shape you wanted.)*

## §2/§6 minor

**2.4 Audit-start acknowledgment** `[A]` — key: `audit_start`
> "That's everything I need. Running your full audit now — every charge, checked against your plan and real prices."

---

## Freeform "Ask Tyndale" opener — PROPOSED, interim engineering seed (2026-08-22)

*Status: INTERIM. These two keys are LIVE in the registry as shippable seed copy (not
`[PLACEHOLDER-eng]`, so they don't block staging) because Brock's 2026-08-22 field test
found the freeform empty state was static copy with nothing to tap. The seed uses Brock's
own words from that feedback. Marked UNMAPPED in the registry until he approves or
re-authors them here, at which point they move into his file and the drift guard covers
them verbatim.*

**Freeform opener** `[A]` — key: `freeform_opener` — client-rendered as the first assistant
bubble of an empty conversation (no LLM call, nothing persisted until the user replies):
> "What can I help you with today?"

**Opener chips** `[A]` — key: `freeform_opener_chips` — four tappable choices under the
opener. Stored as ONE string separated by " · " (the client splits it); each chip is sent
verbatim as the user's first message:
> "Understand a bill · Check if a bill is correct · Think I'm overcharged · Something else"

*Open for Brock: the four labels, the separator convention, and whether "Something else"
should instead route to a typed prompt.*

## Checklist "What is this?" explainers — PROPOSED, interim engineering seed (2026-08-22)

*Status: INTERIM. Eight keys LIVE in the registry as shippable seed copy (not
`[PLACEHOLDER-eng]`) for the checklist explainer affordance (image-3 item 3). Each follows
your asked pattern — what the thing is, where to find it, one concrete example — voice
`[A]`, no invented user-specific numbers (the $2,000 in `explainer_deductible` is a generic
illustrative example). Marked UNMAPPED in the registry until you approve or re-author.*

Keys: `explainer_eob` · `explainer_itemized_bill` · `explainer_sbc` · `explainer_deductible`
· `explainer_deductible_met` · `explainer_oop_max` · `explainer_oop_met` ·
`explainer_visit_confirm` · `explainer_coinsurance` (added 2026-08-27; the coinsurance
checklist item was missing) — full seed texts in
`intelligence-layer/prompts/orchestration_script.md`.

*Open for Brock: the deductible/OOP explainers may carry your tier-1 style example ("your
share moves about $X per $1,000") once the researched figure exists — the seeds deliberately
stop short of one.*

**Checklist completion ack** `[A]` — key: `checklist_item_ack` — one line posted into the
thread when a checklist item is saved (image-3 item 4, "no fanfare"):
> "Got it — {item_label} saved."

## Homescreen banner — PROPOSED, interim engineering seed (2026-08-22)

*Status: INTERIM, from your homescreen mockups. Four keys LIVE as shippable seeds:
`home.banner_title` ("Welcome back, {name}.") + three sublines picked by REAL case state —
`home.banner_subline_empty` / `_active` ("{cases_phrase} — {needs_phrase}.") / `_quiet`.
HONESTY CONSTRAINT on any rewrite: your mockup line "I'm still on your cases — deadlines
watched, numbers re-checked" claims proactive monitoring (B8) that is not built; the test
suite bans those phrases from this surface until B8 exists. Rewrite freely within
what the computed state can truthfully say.*

## Dashboard check-in chips — PROPOSED, interim engineering seed (2026-08-22)

*Note (2026-08-27): these chips are the homescreen TWINS of §9.4 `call_mode.how_did_it_go`
— the same "how did the call go" moment on two surfaces. Author them together (or point
both at one set), or the voices diverge silently.*

*Status: INTERIM, your mockup's own words. Three keys LIVE as seeds — `checkin.fixing_it`
("They're fixing it") / `checkin.pushed_back` ("They pushed back") / `checkin.left_message`
("I left a message"). Doctrine note: these are CALL ROUTES, not outcomes — a tap defers the
real "did it get resolved?" question by the follow-up window rather than retiring it (none
of the three is a resolution; "they said they'd fix it" is a claim by the party we audit).
"Yes, resolved" and "Skip for now" remain the outcome path.*

## Dashboard open-case headlines — PROPOSED, interim engineering seed (2026-08-27)

*Status: INTERIM. Four keys moved out of hardcoded route strings into the registry (audit
item 6) with the shipped words as seeds: `dashboard.headline_unreadable` /
`_finding` ("{category_label} ({finding_type_label})") / `_uploaded` ("Uploaded {doc_type}
— audit pending") / `_open`. Rewrite freely.*

## {itemized_request_script} — PROPOSED, interim engineering seed (2026-08-27)

*Status: INTERIM. The §5.2 slot now resolves (audit group 3) to an engineering-authored
phone script (`runtime/app/ingestion/bill_heuristics.py::ITEMIZED_REQUEST_SCRIPT`):*

> "Hi, I'm requesting a fully itemized bill for my account. The statement I received shows
> only a summary total. Please send an itemized statement that lists every service
> separately with its procedure code (CPT/HCPCS), the date of service, the charge for each
> line, and any payments or adjustments applied. I need the line-level detail to review the
> charges. Thank you."

*Rewrite freely — this renders inside your §5.2 string today.*

## Capture chrome — live keys previously documented nowhere (added 2026-08-27)

Five registry keys ship the camera-capture flow; the label trio is deliberately WITHHELD by
the copy route until you author it (engineering fallbacks render in the app):

| key | state | renders today |
|---|---|---|
| `capture.prompt_bill` | unauthored — withheld; no prompt renders | — |
| `capture.prompt_card` | unauthored — withheld; no prompt renders | — |
| `capture.looks_good` | unauthored — client fallback | "Use this photo" |
| `capture.retake` | unauthored — client fallback | "Retake" |
| `capture.add_page` | unauthored — client fallback | "Take another picture" |

*Design note recorded in the registry comment: the review step deliberately makes NO
"looks readable" claim — we measure (size/blur) and warn on facts only, never a pass.*

## Registry-only appendix — live keys absent from both script docs (added 2026-08-27)

* `system_error_no_email` `[A]` — §10.4 minus the email-promise clause; renders wherever
  `enable_audit_ready_email` is off (it is a RENDER_PATH boot-gate member).
* `finding_no_source` `[A]` — the explicit no-source state on a finding card (E4/H3's
  visible half; a card can never render a bare claim even by omission).
* `reveal.gap_callout` `[A]` — the E3 gap framing on the three-number reveal; suppressed
  server-side on clean/negative/unknown gaps.

## NOT drafted (needs Brock's facts or judgment, per the no-invention rule)
- `{base_rate}` / `{base_rate_source}` — whether a citable base rate EXISTS is yours; the no-rate variant above is the honest default until one does.
- **§10.5 crisis copy** — the routing conflict with DL-04 is a doctrine decision; no draft can resolve it.
- Landing-page statistics (74%/19%/100M+/45%, $504,100, "$400 dispute right") — sourcing questions only, see the decision packet.
- `[B]` tag assignments — which keys are `[B]` is a legal-voice call.
