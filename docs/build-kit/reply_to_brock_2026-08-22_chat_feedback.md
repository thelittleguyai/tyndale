# Phil → Brock — re: your Ask Tyndale chat feedback (2026-08-22)

Great catch — your screenshots let us pin down exactly what's happening. Short version: the intelligence layer isn't broken, and nothing needs to be rebuilt. Two specific problems made it *look* broken, both fixable this week.

**1. Why it looked long and confusing.** Two causes, neither is the rules logic:

- **A rendering bug.** The chat screen renders the assistant's text as plain text — no formatting engine. So the bolding shows as literal `**asterisks**` and the comparison table shows as raw `|---|` pipes. Most of the "hard to follow" in your screenshots is this bug, not the content. Fixing now.
- **No length rules for that surface.** The general chat never got a "you're on a phone, be brief" contract. We're adding one: ~120-word default, no tables, one question per turn, answer-then-ask. Also fixing now.

**2. Important distinction: you were testing the general Q&A chat, not the case flow.** The case-file experience (upload a bill → audit) already works the way you've specced: status cards, grouped verification, tap-to-confirm instead of typing. The general "Ask Tyndale" chat is a separate, lighter surface that hadn't received the same treatment. It is now.

**3. Answer bubbles — yes, building exactly that.** Whenever the next step is a closed choice (yes/no, pick one), the assistant will present tappable chips instead of asking the user to type. Tapping sends the reply. Same mechanism as the verification cards in the case flow.

**4. Your opener — yes, and it's yours to word.** We're adding a scripted opening message with four choice chips. Interim copy (from your message, needs your blessing or rewrite — these become script keys you own, like the rest of the copy registry):

> "What can I help you with today?"
> [Understand a bill] [Check if a bill is correct] [Think I'm overcharged] [Something else]

**5. On "is the intelligence layer working / persistent agent that learns."** The plumbing is verified: the chat does call the retrieval layer (rules, laws, payer knowledge) on every relevant turn, and the case flow runs the full three-number audit. What's limiting quality is that **the knowledge collections are still mostly empty — they're waiting on the corpora and 50-state seed from your content program.** The retrieval engine can't cite rules that aren't ingested yet. Same for the eval rubric: until we can score responses against your rubric, "is it answering well" is subjective. So the two highest-leverage things for exactly the concern you raised are already on your list: the corpora/seed, and the judge rubric. Once the first corpus lands we run the agreed before/after sweep and you'll see the difference measured, not vibes.

The "learning over time" piece (patterns from outcomes feeding back into detection) is designed and staged — it starts accumulating once real cases flow; nothing to rebuild there either.

**One more thing your screenshot caught that you didn't flag:** the reply asserted "error rates as high as 80% on hospital bills" with no source. That violates our own substantiation rule — same class as the $504,100 figure. We're extending the no-unsourced-statistics guard to this chat surface. If you *want* an error-rate stat in the product voice, send the source and it becomes a cited [B] claim; otherwise it speaks qualitatively.

**What I need from you (small):**
1. Opener copy + chip labels — approve the interim above or rewrite (they'll be keys in the v2 script draft).
2. Still open from before: A1–A7 file review, corpora/seed tranches, judge rubric.

Fixes 1–4 ship this week; you'll be able to retest the same flow on your phone.
