# Orchestration Script v2 — DRAFT ADDITIONS for Brock sign-off

**Status: DRAFT — nothing here renders until Brock approves and it ships as v2 of `33_orchestration_script.md`.** The runtime registry cannot be edited directly (CI drift guard). Drafted by Cowork 2026-08-12 in the established v1 voice; **no facts, statistics, citations, or dollar figures invented** — where a variable needs a source of truth that doesn't exist, it's flagged, not filled.

Sections mirror v1 numbering. New keys carry their registry names. `[A]/[B]/[C]` tags per v1 rules.

---

## §3 addition — substance-use-program edge prompt (resolves F2 ↔ §3 conflict IF "author" wins)

**3.6 Elevated prompt — substance-use treatment program** `[A]` — key: `attest.edge_substance`
> "One thing worth knowing: records from a substance-use treatment program carry extra privacy protection — often even from family. If this bill is from one, {patient_name} may need to be the one to bring it to me. Want to continue, or have them take it from here?"

*Modeled on your teen prompt (§3.3): prompt, not a block; same "want to continue, or…" close. If you'd rather DROP the SUD case, delete this and amend checklist F2 instead — your call, both documents can't stand as-is.*

## §4 additions — verification support strings

**4.5 Typed-instead-of-tapped nudge** `[A]` — key: `verification_nudge`
> "Either way works — tap the buttons, or tell me in your own words and I'll mark the card for you to confirm. The tap is what makes it official."

**4.6 Partial-mapping fallback** `[A]` — key: `verification_map_partial_fallback`
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

*⚠️ Dependency: `{claim_number}` is not yet extracted/stored (delta B4). Until it is, this renders the degradation variant — approve the copy anyway and engineering wires the variable.*

**9.7 Provider call opener** `[A]` — key: `call_script_opener_provider`
> "Hi — I'm calling about account {account_number} for {patient_name}, date of service {service_date}. I have a question about a charge before I pay anything."

**9.8 Get it in writing** `[A]` — key: `call_script_get_it_in_writing`
> "Before we hang up — could you send me that in writing? Email or a portal message is fine. And may I have your name and a reference number for this call?"

**9.9 If they push back** `[C]` — key: `call_script_if_they_push_back`
> "I understand — and you don't have to take my word for it. Could you mark the account as disputed while it's reviewed? I'll follow up in writing with exactly what I'm seeing."

**9.10 Call-mode intro** `[A]` — key: `call_mode_intro`
> "You've got this. Everything you need is pinned up top — the numbers, and your script. One step at a time; I'm right here."

**9.11 Call-mode outro** `[A]` — key: `call_mode_outro`
> "That call's done — nice work. How did it go?"

*(Flows into your §9.4 options.)*

## §10 additions

**10.2-alt Guarantee decline, no cited base rate** `[C]` — key: `decline.guarantee_trio_no_rate` — **the launch-default path**
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
`explainer_visit_confirm` — full seed texts in
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

## NOT drafted (needs Brock's facts or judgment, per the no-invention rule)
- `{base_rate}` / `{base_rate_source}` — whether a citable base rate EXISTS is yours; the no-rate variant above is the honest default until one does.
- **§10.5 crisis copy** — the routing conflict with DL-04 is a doctrine decision; no draft can resolve it.
- Landing-page statistics (74%/19%/100M+/45%, $504,100, "$400 dispute right") — sourcing questions only, see the decision packet.
- `[B]` tag assignments — which keys are `[B]` is a legal-voice call.
