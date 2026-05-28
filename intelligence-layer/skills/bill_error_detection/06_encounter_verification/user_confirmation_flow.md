# User confirmation flow

**What this is.** The flow for asking the user to confirm that each translated line item
(from `lineitem_plain_language.md`) matches what actually happened at their visit, and for
converting any mismatch into a candidate finding.

**The flow.**
1. Translate each high-risk line item to plain language (facts only — see
   `lineitem_plain_language.md`).
2. **Bundle the confirmations into ONE message** (per P3 in
   `intelligence-layer/reference/principles.md`) — never a sequence of one-at-a-time
   questions. Present a short, scannable list the user can react to.
3. Use trivial, lived-experience questions ("Were you at the ER for several hours with
   multiple tests, or was it a quick visit?"; "Was blood drawn that day?").
4. Capture each answer against the line item.

**Converting a mismatch into a finding.**
- "Service not received" → candidate **phantom charge**
  (`01_provider_billing/phantom_charges.md`).
- "Coded complexity doesn't match the visit" → candidate **upcoding**
  (`01_provider_billing/upcoding.md`).
- Record the finding as Tier A (what the bill says) + the user's confirmation; the legal
  framing and remediation follow the mapped reference file.

**Boundaries.** Only ask about facts the user can know from being there. Never ask for a
clinical judgment about necessity or appropriateness (out of scope per
`intelligence-layer/reference/refusals.md`).

**Forward compatibility.** In full Tyndale, clinical encounter data augments this step; the
user confirmations captured here are retained as validation labels for the automated
encounter-verification model.
