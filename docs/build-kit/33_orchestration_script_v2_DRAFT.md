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

## Retrieval degradation — PROPOSED, interim engineering seeds (2026-09-23)

*Status: INTERIM. The e2e walk-through (2026-09-23) found the audit running with the rules corpus
unreachable and still shipping a [B] claim (B1), and a guard drop reported to the user as a blurry
photo (B2). Four keys make the degradation honest; all are engineering seeds for Brock to author.
`degraded.missing_input` replaces §5.1 as the fallback for a string whose variable has no value —
§5.1 now renders only on a genuine partial-read signal.*

| key | source | seed |
|---|---|---|
| `retrieval.unavailable_notice` | eng | I couldn't reach my rulebook while I checked this bill, so I stuck to what your documents show and to the math. Anything that would need a rule behind it is marked as worth checking — not stated as a fact. |
| `call_mode.number_on_card` | eng | Use the number on the back of your insurance card. |
| `call_mode.number_on_bill` | eng | Use the phone number printed on your bill. |
| `finding.pending_input` | eng | I need one more thing to firm this up. It's on your checklist. |
| `app.not_found_title` | eng | That page isn't here. |
| `app.not_found_body` | eng | The link may be old, or the address has a typo. Your bills and your record are one tap away. |
| `app.not_found_cta` | eng | Go to my home screen |
| `intake.bill.gloss_eob` / `intake.readiness.gloss_eob` / `intake.limits.gloss_eob` | packet §A2 | (the EOB gloss, on the three screens that now say "Explanation of Benefits (EOB)" instead of "insurer's statement") |
| `finding.no_dollar_change` | eng | No dollar change — still worth fixing. |
| `gameplan.moment_headline` | eng | Your game plan is ready. |
| `gameplan.moment_cta` | eng | See your game plan |
| `grounding.dropped_notice` | eng | I saw one more thing, but I could not tie it back to your papers. So I left it out. I don't guess. |
| `degraded.missing_input` | eng | I don't have what I need to say that part yet. So I left it out. I don't guess. |
| `finding.worth_checking` | eng | Worth checking: there may be a rule behind this, but I couldn't confirm it from a source I could read. Ask about it — don't count on it. |

## E2E re-test fixes — PROPOSED, interim engineering seeds (2026-09-23, afternoon)

*Status: INTERIM. The afternoon re-test found a completed analysis thrown away by one provider
429 on the summary, a status card saying "Audit ready" above an apology, an email promise
nothing kept, and the acknowledgment degrading to the drop line under the spinning card. Each
key below is an engineering seed for you to author; none states a fact the product does not do.*

| key | source | seed |
|---|---|---|
| `summary.pending_notice` | eng | I'm still writing your summary. Your numbers and everything I found are ready now. The summary will show up here when it's done. |
| `status_card.headline_failed` | eng | Paused — a problem on my end |
| `status_card.headline_needs_documents` | eng | Paused — waiting on your documents |
| `status_card.headline_working` / `status_card.headline_ready` | your round-2 prototype, verbatim | Working on your audit / Audit ready — moved from the app into the registry when the header became the server's decision; "Audit ready" now renders ONLY on a complete audit |

## Landing "Not a chatbot with opinions" playback — PROPOSED, interim engineering seeds (2026-09-23)

*Status: INTERIM. The marketing landing's comparison band now PLAYS the two chats side by side
(your round-2 ChatCompare, ported on our tokens — glass still held). The Tyndale pane is registry
copy: five lines are existing keys rendered with the hero fixture's numbers
(`intake.limits.no_accumulator`, `three_number_reveal`, `reveal.gap_callout`, `finding_card_source`
twice, `decline.guarantee_trio_no_rate`); the seven below are new and yours to author. Illustrative
story: an MRI billed $2,347.18; the EOB applied $965.25 to the deductible but two earlier EOBs show
$1,750.00 of the $2,000.00 already met, so only $250.00 belongs on this scan and the member's share
is $612.40 (20% of the remaining $1,812.00 = $362.40 + $250.00), $572.20 under the EOB's $1,184.60.
No statistic anywhere in the Tyndale pane; the citation chips cite the plan's Summary of Benefits
and the member's own EOBs, not a statute — a hand-picked statute on a public page is a legal claim
nobody here can vouch for (the prototype's No Surprises Act line was misapplied to an in-network
overcharge). The OTHER pane — the general chatbot's four replies and their ✗ flags — is marketing
copy like the rest of the page (`apps/web-marketing/src/content/landing-compare.json`), written to
demonstrate the four contrasts you ruled on; it is listed here so you see the whole transcript.*

| key | source | seed |
|---|---|---|
| `landing.compare.user_q1` | eng | My hospital billed me $2,347.18 for an MRI. My insurer says I owe $1,184.60. Is that right? |
| `landing.compare.tyndale_open` | eng | Let me read it, not guess. I have your plan's Summary of Benefits and this EOB. The EOB puts $965.25 toward your deductible. Whether that is right depends on what you had already paid this year. |
| `landing.compare.tyndale_range` | eng | Right now that is **$412.40 to $1,184.60**. Your other EOBs from this year would pin it down. |
| `landing.compare.user_eobs` | eng | I met most of it in February. Here are my other EOBs from this year. |
| `landing.compare.tyndale_deductible` | eng | Got them. Your Feb 3 and Feb 20 EOBs put you at **$1,750.00** of your **$2,000.00** deductible before this scan. So only **$250.00** belongs on this one — not $965.25. |
| `landing.compare.tyndale_plan_rule` | eng | After the deductible, your plan pays 80% of imaging and you pay 20%. 20% of the remaining **$1,812.00** is **$362.40**. |
| `landing.compare.user_win` | eng | Will I win if I dispute it? |

*The foil (not registry; marketing copy):* "Great question! Your insurer's statement lists $1,184.60
as your responsibility, so that figure is most likely correct. For context, an MRI in the U.S.
usually runs somewhere between $400 and $3,500 …" · "I don't have access to your claims, your EOBs,
or anything from earlier conversations …" · "… under Section 12(b) of the Fair Medical Billing Act,
providers must honor a 40% self-pay discount …" (flagged on screen: *Invented — there is no such
law*) · "Most people who dispute a medical bill succeed — studies show around 60% get a reduction
…" (flagged: *A statistic it made up*).

## Guided intake (doc 40) — PROPOSED, interim engineering seeds (2026-09-21)

*Status: INTERIM. Every string the guided `/intake` route renders is LIVE in the registry as a
shippable seed under `intake.<screen>.<slot>` — none is `[PLACEHOLDER-eng]`, all are `[A]`
(none cites law), all are marked UNMAPPED until you author or approve them. Where your packet
gives a line (§A2 glosses, §B6 and §B8 consequence lines, §A7 completeness confirmation and gap
consequence, §A6 "we won't guess", §A8 "nice start", §B1 doctrine line, §B15 facts-only) the
seed is YOUR line, rewritten only as far as grade 5 required; the rest are rewritten CO-1A
strings or engineering seeds. The "from" column says which.*

*Two rules are enforced in CI on these keys from day one (§A6): ≤ 5.9 Flesch–Kincaid (strings
under 7 words use a label rule instead — no word over 3 syllables — because the formula is not
defined on a button), and a glossed term may appear only on a screen that also carries its
`gloss_<term>` key. If you author a line that fails, CI names the key and the score.*

*Reused rather than duplicated: `upload_trust_microcopy` (your §1.2) is the trust line at every
capture (§C10); `dataquality_summary_not_itemized` (your §5.2) is the body of the summary-bill
coaching screen; `wrongdoc.*`, `attest.*`, `system_error*`, `cap_collision` are the edge states
(§C12). Open for you: the four `wrongdoc.*` branches still share one string.*

| key | from | seed |
|---|---|---|
| `intake.chrome.save_exit` | co1a | Save and exit |
| `intake.chrome.saved` | packet §C7 | Saved. You can stop now and come back later. |
| `intake.chrome.see_example` | packet §A3 | See an example |
| `intake.chrome.help_find` | packet §A5 | Help me find it |
| `intake.chrome.email_steps` | packet §A5 | Email me these steps |
| `intake.chrome.email_sent` | eng | Sent. Check your email. |
| `intake.chrome.email_failed` | eng | I could not send that email. The steps are still here on this page. |
| `intake.chrome.continue` | co1a | Continue |
| `intake.chrome.back` | eng | Back |
| `intake.chrome.close` | eng | Close |
| `intake.chrome.open_sample` | eng | Open the sample |
| `intake.chrome.load_error` | co1a | I could not load this step. Your work is saved. Please try again. |
| `intake.chrome.save_error` | co1a | I could not save that. Check your connection and try again. |
| `intake.chrome.retry` | eng | Try again |
| `intake.progress.started` | packet §A8 | {filled} of {total} — nice start |
| `intake.progress.going` | eng | {filled} of {total} done |
| `intake.progress.all` | eng | All {total} done |
| `intake.progress.kept_note` | packet §A8 | I moved one of your papers to a new group. Your progress stays the same. |
| `intake.progress.label_bill` | packet §A8 | Bill |
| `intake.progress.label_card` | packet §A8 | Card |
| `intake.progress.label_plan_rules` | packet §A8 | Plan rules |
| `intake.progress.label_eob` | packet §A8 | EOB |
| `intake.progress.gloss_eob` | packet §A2 | An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it. |
| `intake.progress.label_timeline` | packet §A8 | Timeline |
| `intake.progress.label_about_you` | packet §A8 | About you |
| `intake.progress.label_confirmations` | packet §A8 | Quick checks |
| `intake.resume.title` | packet §C7 | Pick up where you left off. |
| `intake.resume.body` | eng | Your work is saved. Next up: {group_label}. |
| `intake.resume.home_body` | eng | Your bill check is saved. A few more steps and I can run it. |
| `intake.resume.case_label` | eng | Not finished yet |
| `intake.resume.primary` | eng | Keep going |
| `intake.resume.new` | eng | Start a new bill |
| `intake.resume.link_expiry` | packet §C7 | To come back, ask for a new sign-in link. Each link works for {minutes} minutes. |
| `intake.welcome.title` | eng | Let's check your bill. |
| `intake.welcome.body` | eng | I will ask for a few papers, one at a time. I read them for you, so there is little to type. |
| `intake.welcome.doctrine` | packet §B1 | I do not assume the bill is right. I do not assume your insurer is right. I check both. |
| `intake.welcome.primary` | eng | Start with my bill |
| `intake.handoff.title` | eng | Let's finish this in chat. |
| `intake.handoff.body` | eng | This step-by-step path is built for job and self-bought plans so far. For {population_label}, I check your bill in our chat. Nothing you added is lost. |
| `intake.handoff.primary` | eng | Go to chat |
| `intake.handoff.label_medicare` | eng | Medicare |
| `intake.handoff.label_medicare_advantage` | eng | a Medicare plan |
| `intake.handoff.label_medicaid` | eng | Medicaid |
| `intake.handoff.label_dual` | eng | Medicare with Medicaid |
| `intake.handoff.label_self_pay` | eng | a bill with no insurance |
| `intake.handoff.label_tricare_va` | eng | TRICARE or VA coverage |
| `intake.handoff.label_other` | eng | your kind of plan |
| `intake.bill.title` | packet §B2 | Take a photo of your bill. |
| `intake.bill.body` | eng | The itemized bill works best. A photo or a file both work. |
| `intake.bill.gloss_itemized` | eng | Itemized means each charge is on its own line, with a short code next to it. |
| `intake.bill.primary` | eng | Add my bill |
| `intake.bill.no_bill` | packet §B2 | I don't have the bill |
| `intake.bill.no_bill_note` | packet §B2 | That's okay. We can start with your Explanation of Benefits (EOB). |
| `intake.bill_itemized.title` | packet §C5 | This bill is a summary. |
| `intake.bill_itemized.gloss_itemized` | eng | Itemized means each charge is on its own line, with a short code next to it. |
| `intake.bill_itemized.primary` | eng | Add the itemized bill |
| `intake.bill_itemized.secondary` | eng | Keep going with this bill |
| `intake.bill_itemized.secondary_consequence` | eng | I can still check the totals. I can't check each charge. |
| `intake.bill_summary.title` | packet §B5 | Here is what I read. |
| `intake.bill_summary.body` | eng | Take a look. If something is wrong, add a clearer photo. |
| `intake.bill_summary.row_provider` | eng | From |
| `intake.bill_summary.row_date` | eng | Date of visit |
| `intake.bill_summary.row_patient` | eng | Name on the bill |
| `intake.bill_summary.row_account` | eng | Account number |
| `intake.bill_summary.row_missing` | eng | I could not read this |
| `intake.bill_summary.other_bills` | packet §B5 | Did you get other bills for this same visit? |
| `intake.bill_summary.other_bills_why` | packet §C1 | One hospital visit can bring many bills. The doctor, the lab and the hospital may each send one. I check them as one. |
| `intake.bill_summary.yes` | eng | Yes, add another bill |
| `intake.bill_summary.no` | eng | No, that's all |
| `intake.bill_summary.fix` | eng | Something is off |
| `intake.eob.title` | packet §A2 | Now your Explanation of Benefits (EOB). |
| `intake.eob.gloss_eob` | packet §A2 | An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it. |
| `intake.eob.other_name` | packet §A2 | It may have a different name on your insurer's website. |
| `intake.eob.body` | eng | It shows what your insurer paid and what it says you owe. I check that math too. |
| `intake.eob.primary` | eng | Add my EOB |
| `intake.eob.skip` | packet §B6 | I don't have it |
| `intake.eob.skip_consequence` | packet §B6 | I can still check the hospital's charges. But I can't check your insurer's math. That is where the bigger mistakes often are. |
| `intake.card.title` | packet §B7 | Next, your insurance card. |
| `intake.card.body` | co1a | Take a photo of the front and the back. It tells me which plan you have. |
| `intake.card.primary` | eng | Add my card |
| `intake.card.skip` | packet §B7 | I don't have my card |
| `intake.card.skip_consequence` | packet §B7 | That's okay. It may be on your bill. If not, I will ask you to type your insurer's name. |
| `intake.insurer.title` | eng | Who is your insurer? |
| `intake.insurer.body` | eng | I could not find it on your papers. Type it the way it looks on a letter from them. |
| `intake.insurer.body_suggested` | eng | This is what I read on your card. Fix anything that is wrong, then save. |
| `intake.insurer.field_payer` | co1a | Insurer name |
| `intake.insurer.field_member_id` | co1a | Member ID, if you have it |
| `intake.insurer.primary` | eng | Save |
| `intake.insurer.skip` | co1a | Skip for now |
| `intake.insurer.skip_consequence` | eng | Without it, I can't look up your plan. I may need to ask you more. |
| `intake.coverage_type.title` | co1a | How do you get your health insurance? |
| `intake.coverage_type.body` | co1a | This tells me which rules apply to your bill. |
| `intake.coverage_type.opt_job_or_bought` | eng | Through a job, or I bought it myself |
| `intake.coverage_type.opt_medicare` | eng | Medicare |
| `intake.coverage_type.opt_medicaid` | eng | Medicaid |
| `intake.coverage_type.opt_military_va` | eng | TRICARE or VA |
| `intake.coverage_type.opt_none` | co1a | I don't have insurance |
| `intake.coverage_type.opt_not_sure` | eng | I'm not sure |
| `intake.coverage_type.not_sure_consequence` | eng | That's fine. I'll use the rules most plans follow, and I'll say so. |
| `intake.plan_rules.title` | packet §A2 | Now your plan's rulebook. |
| `intake.plan_rules.gloss_sbc` | packet §A2 | It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook. |
| `intake.plan_rules.body` | eng | It is a few pages long. Your insurer's website has it. So does the benefits office at your job. |
| `intake.plan_rules.primary` | eng | Add my SBC |
| `intake.plan_rules.skip` | packet §C9 | I can't find it |
| `intake.plan_rules.skip_consequence` | packet §B8 | Without it, I will show your share as a range, not one number. |
| `intake.plan_rules_confirm.title` | packet §B8 | I may already have your plan's rules. |
| `intake.plan_rules_confirm.body` | packet §B8 | I have these on file for {payer}. Do they match your plan? |
| `intake.plan_rules_confirm.gloss_sbc` | packet §A2 | It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook. |
| `intake.plan_rules_confirm.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.plan_rules_confirm.gloss_out_of_pocket` | eng | The out-of-pocket limit is the most you pay in one plan year. |
| `intake.plan_rules_confirm.gloss_coinsurance` | eng | Coinsurance is your share of the cost after the deductible. |
| `intake.plan_rules_confirm.row_deductible` | co1a | Deductible |
| `intake.plan_rules_confirm.row_oop` | co1a | Out-of-pocket limit |
| `intake.plan_rules_confirm.row_coinsurance` | co1a | Coinsurance |
| `intake.plan_rules_confirm.yes` | co1a | Yes, these match |
| `intake.plan_rules_confirm.no` | co1a | No, something is off |
| `intake.plan_year.title` | packet §B10 | When does your plan year start? |
| `intake.plan_year.body` | packet §A7 | Many plans start in January, but not all. Your deductible starts over on that day. |
| `intake.plan_year.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.plan_year.opt_not_sure` | eng | I'm not sure |
| `intake.plan_year.not_sure_consequence` | eng | That's fine. I just won't know if a month is missing. |
| `intake.timeline.title` | packet §A7 | Your EOBs this plan year. |
| `intake.timeline.gloss_eob` | packet §A2 | An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it. |
| `intake.timeline.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.timeline.body` | packet §A7 | Your deductible adds up over the year. So I need each EOB from the start of your plan year up to this visit. |
| `intake.timeline.visit_marker` | packet §A7 | Your visit |
| `intake.timeline.after_visit` | packet §A7 | After your visit. It does not change this bill. |
| `intake.timeline.no_date` | eng | I could not read a date on this one. |
| `intake.timeline.gap` | packet §A7 | I don't see one for {month}. |
| `intake.timeline.gap_consequence` | packet §A7 | Without it, I'll show your share as a range. |
| `intake.timeline.confirm` | packet §A7 | I count {n} EOBs, {start} to {end}, none for anyone else on your plan. Is that all of them? |
| `intake.timeline.confirm_one` | packet §A7 | I count one EOB, from {start}, and none for anyone else on your plan. Is that the only one? |
| `intake.timeline.confirm_family` | packet §A7 | I count {n} EOBs, {start} to {end}, for {members} people on your plan. Is that all of them? |
| `intake.timeline.confirm_yes` | eng | Yes, that's all |
| `intake.timeline.confirm_no` | eng | No, there are more |
| `intake.timeline.add_more` | eng | Add another EOB |
| `intake.deductible_met.title` | co1a | How much of your deductible had you paid? |
| `intake.deductible_met.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.deductible_met.body` | eng | I mean before this visit, in this plan year. Your insurer's website shows it. |
| `intake.deductible_met.field_amount` | co1a | Amount paid so far |
| `intake.deductible_met.primary` | eng | Save |
| `intake.deductible_met.not_sure` | eng | I'm not sure |
| `intake.deductible_met.not_sure_consequence` | packet §A6 | We don't know what you'd already paid by then, so we won't guess. I will show your share as a range. |
| `intake.oop_met.title` | co1a | How much counted toward your out-of-pocket limit? |
| `intake.oop_met.gloss_out_of_pocket` | eng | The out-of-pocket limit is the most you pay in one plan year. |
| `intake.oop_met.body` | eng | I mean before this visit, in this plan year. Your insurer's website shows it. |
| `intake.oop_met.field_amount` | co1a | Amount paid so far |
| `intake.oop_met.primary` | eng | Save |
| `intake.oop_met.not_sure` | eng | I'm not sure |
| `intake.oop_met.not_sure_consequence` | packet §A6 | We don't know what you'd already paid by then, so we won't guess. I will show your share as a range. |
| `intake.attest.title` | packet §B13 | Who is this bill for? |
| `intake.attest.primary` | eng | I confirm |
| `intake.attest.decline` | eng | I can't confirm this |
| `intake.attest.back_home` | eng | Back to home |
| `intake.other_insurance.title` | packet §B14 | Do you have a second health plan? |
| `intake.other_insurance.body` | packet §B14 | Some people are on two plans. If you are, I check it. I don't assume it pays the rest. |
| `intake.other_insurance.yes` | eng | Yes |
| `intake.other_insurance.no` | eng | No |
| `intake.other_insurance.not_sure` | eng | I'm not sure |
| `intake.other_insurance.not_sure_consequence` | eng | That's fine. I'll check this bill with the one plan I know. |
| `intake.reading.title` | packet §B4 | Reading your bill. |
| `intake.reading.body` | eng | This takes a minute or two. You can leave and come back. Your work is saved. |
| `intake.facts_only.title` | packet §B15 | A few quick facts about your visit. |
| `intake.facts_only.body` | packet §B15 | I only ask what happened. I never ask if the care was right. That is between you and your doctor. |
| `intake.facts_only.primary` | eng | Okay |
| `intake.confirmations.title` | packet §B16 | Did these happen? |
| `intake.confirmations.body` | eng | Each one is a charge on your bill, in plain words. Tell me if it happened. |
| `intake.confirmations.yes` | co1a | Yes |
| `intake.confirmations.no` | co1a | No |
| `intake.confirmations.not_sure` | packet §B16 | I'm not sure |
| `intake.confirmations.not_sure_note` | packet §B16 | That's fine. I will mark it as not settled. |
| `intake.confirmations.primary` | eng | Done |
| `intake.readiness.title` | packet §B17 | Here is what I have. |
| `intake.readiness.body` | packet §B17 | You can run the check now. Or add what is missing first, for a sharper answer. |
| `intake.readiness.resolved` | eng | Have it |
| `intake.readiness.unresolved` | eng | Missing |
| `intake.readiness.skipped` | eng | Skipped |
| `intake.readiness.edit` | packet §B17 | Change |
| `intake.readiness.primary` | eng | Check my bill |
| `intake.readiness.cannot_run` | eng | Add a bill or an insurer statement first. I need one of them to check. |
| `intake.readiness.item_bill` | eng | Your bill |
| `intake.readiness.item_itemized_bill` | eng | A bill with each charge listed |
| `intake.readiness.item_eob` | eng | Your Explanation of Benefits (EOB) |
| `intake.readiness.item_payer` | eng | Your insurer |
| `intake.readiness.item_plan_rules` | eng | Your plan's rulebook |
| `intake.readiness.item_plan_year_start` | eng | When your plan year starts |
| `intake.readiness.item_eob_completeness` | eng | All your EOBs |
| `intake.readiness.item_deductible_met` | eng | What you had paid before this visit |
| `intake.readiness.item_oop_max_met` | eng | What counted toward your yearly limit |
| `intake.readiness.item_coverage_type` | eng | Your kind of coverage |
| `intake.readiness.item_attestation` | eng | Who the bill is for |
| `intake.readiness.item_other_insurance` | eng | A second health plan |
| `intake.readiness.item_encounter_facts` | eng | Facts about your visit |
| `intake.limits.no_bill` | eng | No bill yet. I can only check your Explanation of Benefits (EOB). |
| `intake.limits.summary_bill` | packet §C5 | This bill shows totals only. I can't check each charge. |
| `intake.limits.no_eob` | packet §B6 | No EOB. I can't check your insurer's math. |
| `intake.limits.no_payer` | eng | I don't know your insurer. Some plan rules can't be checked. |
| `intake.limits.no_plan_rules` | packet §B8 | No plan rulebook. Your share becomes a range. |
| `intake.limits.no_plan_year` | packet §A7 | I don't know when your plan year starts. I can't place your visit in the year. |
| `intake.limits.incomplete_eobs` | packet §A7 | Some EOBs may be missing. Your share becomes a range. |
| `intake.limits.no_accumulator` | packet §A6 | I don't know what you had paid so far. Your share becomes a range. |
| `intake.limits.no_coverage_type` | eng | I don't know your kind of coverage. I will use the common rules. |
| `intake.limits.no_other_insurance` | eng | I don't know if you have a second plan. |
| `intake.limits.no_confirmations` | eng | Visit facts are not checked yet. Some charges stay open. |
| `intake.analysis.title` | packet §B18 | Checking your bill. |
| `intake.analysis.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.analysis.step_read` | eng | Reading your papers |
| `intake.analysis.step_position` | packet §B18 | Working out where your deductible stood |
| `intake.analysis.step_provider` | packet §B18 | Checking the bill's side |
| `intake.analysis.step_payer` | packet §B18 | Checking your insurer's side |
| `intake.analysis.leave` | eng | This can take a few minutes. You can leave. I will keep working. |
| `intake.unlock.headline` | your §7.1 `unlock.card`, minus the price clause | {gap} of this should not be yours to pay. Your plan to fix it is ready. |
| `intake.unlock.proceed` | eng | See my plan |
| `intake.unlock.free_beta` | prompt item 8 | Free while we're in beta. |
| `intake.unlock.blocked` | eng | This step is not open yet. |
| `intake.example.gloss_sbc` | packet §A2 | It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook. |
| `intake.example.gloss_msn` | packet §A2 | An MSN is the Medicare Summary Notice. Medicare mails it to show what it paid. |
| `intake.example.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.example.gloss_out_of_pocket` | eng | The out-of-pocket limit is the most you pay in one plan year. |
| `intake.example.source_federal` | packet §A3 | This sample comes from the U.S. government. It is not your plan. |
| `intake.example.sbc_title` | packet §A3 | A sample SBC |
| `intake.example.sbc_1` | packet §A3 | Top right: the coverage period. The first date is when your plan year starts. |
| `intake.example.sbc_2` | packet §A3 | First row: the overall deductible, for one person and for a family. |
| `intake.example.sbc_3` | packet §A3 | Third row: other deductibles, like one just for drugs. |
| `intake.example.sbc_4` | packet §A3 | Fourth row: the out-of-pocket limit. It lists one number in the network and one out of it. |
| `intake.example.sbc_5` | packet §A3 | Page 2: two columns of costs. One is for network doctors. One is for doctors outside it. |
| `intake.example.sbc_6` | packet §A3 | Last page: three made-up patients. They show how the plan splits a real bill. |
| `intake.example.msn_title` | packet §A3 | A sample MSN |
| `intake.example.msn_1` | packet §A3 | Top of page 1: the words "This is not a bill." |
| `intake.example.msn_2` | packet §A3 | Page 1: the box named "Your Deductible Status." It shows how much you have met. |
| `intake.example.msn_3` | packet §A3 | Page 1: "Total You May Be Billed" for this period. |
| `intake.example.msn_4` | packet §A3 | Page 3: the claims table. The last column is the most the doctor may bill you. |
| `intake.example.msn_5` | packet §A3 | Last page: how to appeal, and the date you must do it by. |
| `intake.help.title` | packet §A5 | Where to find it |
| `intake.help.generic_note` | packet §A5 | These are general steps. Your insurer's website may use other names. |
| `intake.help.payer_note` | packet §A5 | These steps are for {payer}. |
| `intake.help.gloss_eob` | packet §A2 | An EOB is the statement your insurer sends after a visit. It says "This is not a bill" on it. |
| `intake.help.gloss_sbc` | packet §A2 | It is called the Summary of Benefits and Coverage (SBC). Think of it as your plan's rulebook. |
| `intake.help.gloss_deductible` | packet §A6 | The deductible is the amount you pay before insurance starts paying. |
| `intake.help.gloss_out_of_pocket` | eng | The out-of-pocket limit is the most you pay in one plan year. |
| `intake.help.gloss_itemized` | eng | Itemized means each charge is on its own line, with a short code next to it. |
| `intake.help.email_subject` | eng | Your steps from Tyndale |
| `intake.help.email_intro` | eng | Here are the steps you asked for. Come back to Tyndale when you have it. |
| `intake.help.eob_1` | eng | Sign in to your insurer's website or app. |
| `intake.help.eob_2` | eng | Look for Claims. It may be called Claims and Payments. |
| `intake.help.eob_3` | eng | Find the claim with your visit date. Open it. |
| `intake.help.eob_4` | eng | Look for a link that says EOB, or View Statement. Save it as a file. |
| `intake.help.eob_5` | eng | No luck? Call the number on the back of your card. Ask them to mail or email the EOB. |
| `intake.help.sbc_1` | eng | Sign in to your insurer's website or app. |
| `intake.help.sbc_2` | eng | Look for Plan Documents or Benefits. |
| `intake.help.sbc_3` | eng | Open the file named Summary of Benefits and Coverage. Save it. |
| `intake.help.sbc_4` | eng | Got your plan at work? Your benefits office has it too. They must give it to you when you ask. |
| `intake.help.insurance_card_1` | eng | Check your wallet, or a drawer with your mail from the insurer. |
| `intake.help.insurance_card_2` | eng | No card? Sign in to your insurer's app. Look for ID Card. You can save a copy. |
| `intake.help.insurance_card_3` | eng | Still no card? Your bill or EOB may show the insurer and your member ID. |
| `intake.help.itemized_bill_1` | eng | Call the billing number on your bill. |
| `intake.help.itemized_bill_2` | eng | Ask for the itemized bill, with every charge and its code. |
| `intake.help.itemized_bill_3` | eng | Give them your account number and your visit date. |
| `intake.help.itemized_bill_4` | eng | They can mail it, email it, or post it on their website. There is no charge. |
| `intake.help.accumulators_1` | eng | Sign in to your insurer's website or app. |
| `intake.help.accumulators_2` | eng | Look for Deductible, or Plan Balances. It is often on the first page. |
| `intake.help.accumulators_3` | eng | Write down the amount you have paid so far, and the date it shows. |
| `intake.help.plan_year_1` | eng | Look at the top of your SBC. Find the words Coverage Period. |
| `intake.help.plan_year_2` | eng | The first date is the day your plan year starts. |
| `intake.help.plan_year_3` | eng | No SBC? Your benefits office or your insurer can tell you the date. |

## NOT drafted (needs Brock's facts or judgment, per the no-invention rule)
- `{base_rate}` / `{base_rate_source}` — whether a citable base rate EXISTS is yours; the no-rate variant above is the honest default until one does.
- **§10.5 crisis copy** — the routing conflict with DL-04 is a doctrine decision; no draft can resolve it.
- Landing-page statistics (74%/19%/100M+/45%, $504,100, "$400 dispute right") — sourcing questions only, see the decision packet.
- `[B]` tag assignments — which keys are `[B]` is a legal-voice call.
