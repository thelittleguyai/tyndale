# How Tyndale Works — Target End-State Behavior

> **Purpose of this document.** This is a reference for the Tyndale build. It
> describes, through one thorough use case, what Tyndale should *do* and *feel
> like* when it's working correctly — the end-state behavior the build is aiming
> at. Use it as context when building, and as a yardstick: if what you've built
> doesn't behave like the Tyndale described here, it isn't done.
>
> This is a behavior spec told as a story, not a technical spec. For the
> technical architecture see the Developer Build Spec; for the build tasks see
> the Build Kit; for the foundational doctrines see `reference/principles.md`.
> This document shows what all of that should add up to from the user's seat.
>
> Applies to both versions. Where V1-Lite and Full V1 differ, both paths are
> described. The brain (the audit, the grounding, the advocacy) is identical in
> both; only how Tyndale acquires the user's data differs.

---

## The one-paragraph version

Tyndale is an AI advocate that audits medical bills the way an expert would. It
does not trust the provider's bill or the insurer's statement — it treats both
as claims to be checked. It independently computes what the user *should* owe
from their real coverage terms and the real rules, then compares that against
what was billed and what the insurer claims, and the gaps are the findings.
Everything it asserts is grounded in authoritative data (real codes, rules, law,
and the user's own documents/records), never the model's memory. It thinks
several steps ahead, asks for what it needs in one trivial batch rather than
interrogating, never dead-ends when data is missing, and hands the user a calm,
prioritized, scripted plan instead of an overwhelming dump. In V1-Lite the user
uploads their own documents and Tyndale coaches them to act; in Full V1 Tyndale
connects to the user's insurance and records and acts for them.

---

## The use case: Maya's burst appendix

Three weeks ago Maya had emergency surgery for a burst appendix. She went to the
nearest ER at 2am, was admitted, had the appendix removed, stayed two nights,
went home. Now the mail is arriving and it's chaos: a bill from the hospital, a
separate bill from the surgeon, a third from an anesthesiologist she never met,
and a confusing statement from her insurer. The total is over $14,000. She has
no idea what's right, what's wrong, or where to start. She is overwhelmed.

This is the exact moment Tyndale is for. Here is how it should behave, end to
end.

---

### Stage 1 — Take the chaos and organize it

Tyndale does not open with a form. It says, in effect: "Let's take this one
piece at a time. Snap a photo of whatever you've got — bills, the insurance
statement, your insurance card — and I'll sort it out." Maya uploads four
crumpled photos.

**Under the hood:** Tyndale turns messy images into organized facts. It reads
and classifies each document — hospital facility bill, surgeon's professional
fee, anesthesiologist's bill, insurer's Explanation of Benefits (EOB) — and
extracts the structured details from each: procedure codes, dollar amounts,
dates of service, provider names.

**The capability that matters:** Tyndale recognizes these four documents are
*one event*, not four problems. It opens a single **case file** — the folder a
good human advocate would open — and files all four documents into it, linked to
the same appendectomy on the same dates. From here on, everything Tyndale learns
lives in that case file. That is how it maintains context: not a fuzzy
conversation held in its head, but a structured, durable record every part of
the system reads from and writes to. When Maya returns next week, the folder is
still there, complete.

---

### Stage 2 — Figure out what it knows, what it needs, and ask for everything at once

Before any analysis, Tyndale takes stock — this is where "thinking ten steps
ahead" begins. It maps what it will *need* to fully audit this event: Maya's
coverage terms (deductible, coinsurance, out-of-pocket max, and how much she'd
already used this year), whether the hospital was in-network, whether each
separate provider was in-network, and what actually happened during the stay so
it can verify the charges.

It checks the case file. The insurance card gave it her plan, her $3,000
deductible, and 20% coinsurance. It's missing two things: how much of the
deductible she'd met before surgery, and whether the anesthesiologist was
in-network.

**The capability that matters — bundle questions, never interrogate.** A lesser
tool asks one question, waits, asks another, waits. Tyndale figures out
*everything* it needs up front and asks in one clean message, with context for
each ask and instructions for finding each answer:

> "I've got your four bills organized. To check whether your insurer calculated
> these correctly, I need two things — and here's exactly where to find each:
> (1) How much of your $3,000 deductible had you used this year before the
> surgery? You can see this in your insurer's app under 'spending summary,' or
> call the number on your card and ask 'how much of my deductible have I met
> this year?' (2) Do you have the EOB for the anesthesiologist, or just the
> hospital and surgeon? If you're not sure, no problem — just tell me what you
> have."

**Why this matters:** this is "make the ask trivial." Maya isn't asked to
understand insurance — she's asked two concrete questions, each with a map to
the answer. And Tyndale already did everything it *could* without bothering her;
it only asked for the two things it genuinely couldn't get on its own.

---

### Stage 3 — Where the data comes from (the two versions diverge here)

This is the heart of accuracy, and the exact point where V1-Lite and Full V1
differ. Both feed the *same* audit engine; they acquire raw material
differently.

**V1-Lite (manual).** Maya is the source. She uploads documents and answers the
two targeted questions. For the clinical side — what actually happened during
the stay — Tyndale can't pull her records, so it works from what's on the bills
and confirms specifics with her in plain language (Stage 5). Design point:
Tyndale extracts the maximum from minimal effort — it reads documents rather
than making her type, and confirms only what it's unsure about.

**Full V1 (automatic, via 1upHealth).** Maya taps "connect my insurance" once.
From then on Tyndale pulls her data directly and continuously — real coverage
terms, deductible status to the dollar, full claims history, the network status
of every provider, *and* her clinical encounter records (what was actually done
during the stay). She uploads nothing. The two questions Tyndale had to ask in
V1-Lite, it already has answered in Full V1.

**Why it upgrades cleanly:** the audit engine doesn't know or care where the
data came from. In both versions the coverage terms land in the same place in
the case file, in the same shape. So when data arrives from 1upHealth instead of
a photo, every downstream step — math, error detection, legal analysis — works
*identically*. The upload path stays as a fallback for users who'd rather not
connect, or whose insurer isn't reachable.

**The reference data underneath both (why it's expert, not guessing):** to
evaluate Maya's bills, Tyndale looks up real facts from maintained libraries —
what each procedure code means, the government's official rules about which codes
can and can't be billed together, the actual text of federal and state law, and
her insurer's own published policies. It *retrieves* these; it never recalls them
from memory. If it can't ground a claim in a real source, it stays silent rather
than inventing one. That discipline — **no source, no claim** — is the line
between a trustworthy tool and a confident-sounding chatbot. The law and policies
are also time-stamped, so Maya's surgery is judged against the rules in force on
*her* date of service, not a blurred average.

---

### Stage 4 — Do the math independently, then audit both sides

Maya answers: she'd met $2,400 of her $3,000 deductible before surgery. Tyndale
now computes what she *should* owe — from scratch, before looking at what the
insurer claims.

The hospital's allowed amount was, say, $9,000. With $600 of deductible left,
that $600 applies first, then 20% coinsurance applies to the remainder up to her
out-of-pocket max. Tyndale works it through to an independent number.

Then — and only then — it compares three numbers: what the hospital billed, what
the insurer's EOB says she owes, and what Tyndale computed. It finds the insurer
applied $3,000 to her deductible, as if she'd met none of it that year. That's a
$2,400 error — and it's the *insurer's* mistake, not the hospital's.

**Why this is the whole point.** Maya, like almost everyone, would have read the
official-looking insurer statement and assumed it was right. Tyndale catches it
because it never trusted the statement — it treats the EOB as a *claim to be
audited,* not an answer. Half of what Tyndale catches lives in this blind spot,
and no general chatbot reaches it, because no general chatbot independently
recomputes the answer from the real coverage terms.

---

### Stage 5 — Verify the care actually happened as billed

Tyndale turns to the charges. On the itemized hospital bill it sees "operating
room time — 4 hours."

**V1-Lite:** Tyndale can't see Maya's records, so it translates the charge into
plain English and asks her to confirm against memory: *"Your hospital bill
includes four hours of operating room time. Appendectomies are usually under two
hours. Does four hours sound right, or was it shorter?"* Maya says it felt like
about an hour and a half. Tyndale flags a potential overcharge to investigate —
not as a certainty, but as a lead.

**The careful line:** Tyndale only asks Maya about *facts she can know* — how
long she was in surgery, whether she received a medication, whether she saw a
particular doctor. It never asks her to judge whether something was *medically
necessary* — that's a clinical question, and Tyndale is a billing advocate, not
a doctor. This boundary is hard-coded.

**Full V1:** this is largely automatic — Tyndale pulls the clinical encounter
record from 1upHealth and checks billed time and items against what the records
show, only involving Maya if there's a discrepancy to confirm. Strategic payoff:
every plain-language confirmation Maya gives in V1-Lite becomes labeled data that
teaches the automated version what "matches / doesn't match" looks like. The lean
version trains the full version.

---

### Stage 6 — Catch the surprise out-of-network bill using the law

Tyndale checks the anesthesiologist's bill — a provider Maya never chose. It
finds the anesthesiologist was out-of-network even though the hospital was
in-network, and the bill is for the full out-of-network amount.

Tyndale retrieves the actual text of the federal No Surprises Act, filtered to
the rules in force on Maya's date of service, and recognizes the fit: for
emergency care, or care at an in-network facility from an out-of-network provider
the patient didn't choose, the patient generally can't be balance-billed beyond
in-network cost-sharing. Maya was unconscious; she didn't pick her
anesthesiologist. This bill appears to violate that law.

**How it phrases this:** dollar facts stated flatly (they're computed); the legal
conclusion framed carefully — "this *appears to violate* the No Surprises Act" —
with the citation attached to the actual provision. It won't overclaim ("this is
illegal fraud") and won't predict the outcome ("you'll win"), because an honest
advocate doesn't promise results. That calibrated honesty is what makes it
defensible rather than reckless.

---

### Stage 7 — Think ahead about what to do when something's missing

Suppose Maya *didn't* have the anesthesiologist's EOB and couldn't find it. A
brittle tool stalls: "I need that document to continue." Tyndale branches instead
of dead-ending.

It reasons through alternatives: it can still tell Maya, from the bill alone,
that this looks like a surprise out-of-network charge protected by law; it can
tell her the EOB would let it confirm the exact overcharge; and it can hand her
precise steps to get the EOB — *"Log into your insurer's portal, go to 'claims,'
and look for one dated [surgery date] from [anesthesia group]; or call and ask
them to resend it. Want me to remind you to upload it once you have it?"* It
delivers value with what it has, names what's missing, helps her get it, and
keeps moving. Its usefulness is never held hostage to perfect inputs.

---

### Stage 8 — Hand the user a calm, prioritized, non-overwhelming plan

Tyndale has now found three things across four documents: a $2,400 deductible
error by the insurer, a likely operating-room-time overcharge, and an illegal
surprise bill from the anesthesiologist. A worse tool dumps all of this at once
and leaves Maya paralyzed. Tyndale spoon-feeds.

It leads with the headline in plain language: *"Good news — I found about $X you
shouldn't have to pay. There are three separate issues here, but you don't need
to handle them all at once. Let's start with the easiest, biggest win."* Then it
gives **one** clear first action — the insurer's deductible error, the largest
and most clear-cut — with a scripted phone call: the number, the claim to
reference, the exact sentence to say. It sets a deadline reminder. It tells her
the other two issues are queued and it'll walk her through each next, so she
knows nothing is dropped.

**Hand-holding by design:** one step at a time, biggest win first, every action
scripted, nothing ambiguous, and a constant sense that Tyndale is carrying the
mental load. In Full V1 the "make a phone call" step is replaced — Tyndale drafts
the corrected-claim letter and the No Surprises Act dispute, cites the law, and
sends them on her behalf with one tap of her approval.

---

### Stage 9 — Stay on the case after she closes the app

Tyndale doesn't go quiet after giving advice. It set deadlines, so it watches
them. If the insurer doesn't respond to the deductible correction within a couple
of weeks, it nudges Maya: *"It's been 14 days and we haven't heard back on your
deductible correction — want me to walk you through the follow-up call?"* When a
corrected EOB arrives, it re-runs the audit automatically to confirm the fix
landed. And it closes the loop with the question that quietly makes the product
smarter: *"Did this get resolved? How much did you get back?"* — which, with her
consent and her personal details stripped out, becomes a real-world outcome that
improves Tyndale for the next person.

---

## The capabilities, summarized (the checklist for "is it behaving like Tyndale?")

Everything in Maya's story rests on these commitments. If the build is working,
all of these should be observably true:

1. **Organizes chaos into a structured case file** and reasons from that durable
   context, not a fuzzy in-session memory. Returns later find the folder intact.
2. **Grounds every fact in real, maintained data** — codes, rules, law, the
   user's own coverage/records — and refuses to assert anything it can't source.
   No source, no claim.
3. **Time-aware grounding:** judges each claim against the rules in force on the
   date of service.
4. **Computes independently and audits both sides** — provider bill *and* insurer
   EOB — surfacing three numbers and naming which side each gap is on.
5. **Treats the EOB as a claim, never as truth.** This is non-negotiable and is
   how it catches payer-side errors that hide on official letterhead.
6. **Verifies the care happened as billed** — by user confirmation in V1-Lite, by
   clinical records in Full V1 — and only ever asks the user about facts, never
   clinical judgment.
7. **Thinks several moves ahead:** bundles questions into one trivial ask,
   branches gracefully when data is missing, and never dead-ends.
8. **Hand-holds without overwhelming:** one prioritized step at a time, biggest
   win first, every action scripted.
9. **Speaks with calibrated honesty:** facts stated plainly, legal claims cited
   and qualified, recommendations reasoned, outcomes never predicted.
10. **Stays a proactive advocate after the conversation ends:** tracks deadlines,
    re-audits when new documents arrive, follows up, and captures outcomes (with
    consent + de-identification) to improve over time.

---

## V1-Lite vs Full V1 — the only real difference

The difference is *how much the user has to do themselves.*

- **V1-Lite** coaches the user through it with everything scripted. The user
  uploads their own documents; Tyndale confirms specifics in plain language;
  Tyndale tells the user exactly what to say and do; the user makes the calls and
  sends the disputes.
- **Full V1** connects to the user's insurance and clinical records (via
  1upHealth or equivalent) and does the work for them — pulling data
  automatically, drafting the letters, and sending the disputes on the user's
  approval.

The brain — the audit, the grounding, the advocacy, the voice — is identical in
both. V1-Lite is a real, valuable product on day one *and* a running start toward
Full V1, not a throwaway. Every bill, confirmation, and outcome captured in
V1-Lite (with consent and de-identification) makes Full V1 better, especially the
automated letter-writing, which gets built on real cases with known outcomes
rather than from theory.

---

## How to use this document in the build

- Treat it as the **acceptance narrative**: when a feature is built, check it
  against the relevant stage and the capability checklist above.
- When a build decision is ambiguous, ask "which choice makes Tyndale behave more
  like the Tyndale in this document?" and choose that one.
- This document describes *behavior and end-state*, not implementation. It
  intentionally doesn't dictate code structure — see the Developer Build Spec and
  Build Kit for that. The doctrines that make this behavior non-negotiable live in
  `reference/principles.md` (the Independent Audit Doctrine and the Grounding &
  Graceful Degradation Doctrine).
