# Change Order 001 — Re-add four concepts from the original intelligence-layer design

**To:** Claude Cowork (Tyndale build PM/product manager)
**From:** Brock
**Status:** Approved — incorporate into the V1-Lite build
**Type:** Additive change order. Nothing here removes or contradicts existing
locked decisions, doctrines, or the V1-Lite scope. These four items were present
in an earlier intelligence-layer concept, were validated in a gap analysis as
still valuable, and are being re-added.

---

## Why this change order exists

A gap analysis compared the current Tyndale intelligence-layer build against an
earlier "four systems / five workflows" concept document. Most of the old concept
was already carried forward (and improved). Four concrete ideas from the old
version were NOT fully captured in the current build and are worth re-adding. This
change order adds them. (The old n8n/five-workflow architecture, the Ideon/Stedi
vendors, and the EOB-as-input framing were deliberately NOT brought back — the
current Agent-SDK architecture, 1upHealth, and the Independent Audit Doctrine
supersede them.)

These four apply to **V1-Lite** (and carry forward to Full V1 unchanged). They are
behavioral/structural, forward-compatible, and low-risk.

---

## The four additions

### 1. An always-loaded Agent behavioral core + a growing "worked examples" library

**What to add.** Today, Tyndale's behavioral spec (identity, the interaction
principles, the doctrines, voice tiering) is distributed across reference files
that are retrieved as needed. Re-add the original concept's guarantee: a **core
behavioral spec that is loaded IN FULL at the start of every session / Lead Planner
invocation — never similarity-searched, never dependent on a retrieval call
succeeding.** It is unconditionally present in every interaction.

The behavioral core must contain, at minimum:
- Tyndale's identity and role (proactive patient advocate; does the thinking so
  the user doesn't have to; never waits to be asked).
- The interaction principles (P1–P6).
- The two foundational doctrines (Independent Audit; Grounding & Graceful
  Degradation).
- The silent case-intake checklist (run on every new bill before responding).
- The proactive thinking loop (see item 2).
- The "always do" rules (surface the supporting law, state deadlines, end with
  clear next steps, etc.).
- The confidence/escalation protocol (distinguish confirmed errors from items
  worth investigating; flag uncertainty, never hide it).
- **A "worked examples" section that GROWS OVER TIME** — concrete examples of
  wrong-vs-right agent behavior. When a mistake is caught (via the feedback loop
  or Brock's review), the corrected behavior is added here as a worked example so
  the agent doesn't repeat it. This complements (does not replace) the eval suite:
  the eval suite tests behavior; the worked-examples library teaches it in-context.

**Why it matters.** A retrieved behavioral spec can silently fail to load; a
guaranteed-in-context core cannot. This raises the behavioral floor on every single
interaction. The growing worked-examples library is a cheap, high-leverage way to
encode "never make this mistake again."

**Where it goes.** Update the principles foundation (build kit Task 02) and the
Lead Planner prompts (Task 16 full; V1-Lite collapsed Lead Planner, Task L04) so
the behavioral core is assembled and injected in full at session start. Add a
`worked_examples` reference file that the feedback-loop triage (Task L06) can append
to. Confirm the assembled core fits the context budget; if it grows large, prioritize
identity + principles + doctrines + thinking loop + confidence protocol as the
non-negotiable always-loaded portion, with worked examples loaded as space allows
(most-recent / most-relevant first).

**Done when.** The Lead Planner provably receives the full behavioral core on every
invocation without a retrieval dependency, and there is a worked-examples file the
correction/feedback process appends to.

---

### 2. An explicit, enumerated proactive thinking loop run before every response

**What to add.** Re-add the original concept's concrete pre-response checklist —
the questions the agent asks itself before EVERY response. Make it an explicit,
written checklist in the behavioral core (not merely implied by the principles):

- What do I now know?
- What's still unknown — and what's the most important missing piece?
- What hasn't the user asked about that could affect their outcome?
- Are there any deadlines I need to surface?
- Should I generate or recommend a document/action right now?
- Is there a relevant law, rule, or policy I should ground this in?
- What is the single most important thing for the user right now?

**Why it matters.** The principles imply this, but an enumerated checklist produces
more consistent proactive behavior from the model than implicit guidance does.

**Where it goes.** Add as a named section in the behavioral core (item 1), and
reference it in both Lead Planner prompts (Task 16 and Task L04). In V1-Lite,
align the "should I generate a document" question with the deferral (V1-Lite gives
a scripted action, not a drafted letter) — the question becomes "should I give a
specific next action right now?"

**Done when.** Both Lead Planner prompts instruct the agent to run this enumerated
loop before composing any response.

---

### 3. Lead with a status update on app open — not "how can I help?"

**What to add.** Re-add the original concept's open-with-status behavior: when a
returning user opens the app, Tyndale loads their open cases and recent context and
**opens by telling them where things stand** ("Here's where your three open issues
are — the deductible correction is still pending with your insurer; it's been 9
days") rather than a blank "How can I help?" prompt.

**Why it matters.** It's a concrete, high-impact expression of proactivity and the
"stay on the case after the conversation ends" behavior in the acceptance narrative.
It materially changes how the product feels — like an advocate who remembers and is
already working, not a chatbot waiting for input.

**Where it goes.** Specify in the V1-Lite web app behavior (Task L08) and in the
Lead Planner's session-open behavior (Tasks 16 and L04). On app open: load open
cases + recent conversations + any due/overdue next_actions, and compose a status-
forward opening message. If there are no open cases, fall back to a warm, brief
prompt.

**Done when.** A returning user with open cases sees a status-forward opening
message; the behavior is driven by loaded case state, not a static greeting.

---

### 4. Add a `research_log` field to the case file

**What to add.** Re-add the original concept's `research_log` — a structured field
on the case that records **what the agent has already investigated**, so it doesn't
redundantly re-run the same lookups or re-ask the user across sessions.

Suggested shape (confirm against the existing case-file schema):
- `research_log`: array of entries, each `{timestamp, topic/question, what_was_
  checked (e.g., which collection/source/tool), result_summary, finding_id (if it
  produced one)}`.

**Why it matters.** Prevents redundant investigation (saves tokens and latency) and
makes the agent feel like it genuinely remembers — it won't re-ask what it already
resolved. Pairs naturally with the case file and the proactive thinking loop (the
loop's "what do I now know" question reads the research_log).

**Where it goes.** Add to the case-file schema (the PostgreSQL case-file definition
in the Developer Build Spec / the collection-and-schema work, build kit Task 23 and
the Postgres schema). Ensure both Lead Planner prompts write to it as they
investigate and read it before re-investigating. Forward-compatible with Full V1
unchanged.

**Done when.** The case-file schema includes `research_log`, the Lead Planner writes
entries as it investigates, and it consults the log before repeating a lookup.

---

## Scope, sequencing, and guardrails for Cowork

- **All four are additive and forward-compatible.** None changes the V1-Lite scope,
  the doctrines, the pricing, or the upgrade path. Items 1–3 are behavioral spec +
  prompt changes; item 4 is a schema addition.
- **Sequence:** fold items 1 and 2 together (the behavioral core houses the thinking
  loop). Item 4 (schema) should land before or with the case-file build so it isn't
  a later migration. Item 3 depends on the case file + Lead Planner being in place.
- **Do not** use this change order as license to re-introduce the old n8n/five-
  workflow architecture, the Ideon/Stedi vendors, or any EOB-as-truth framing —
  those were intentionally superseded.
- **Keep the behavioral core within the context budget.** If it grows, the
  always-loaded non-negotiable portion is identity + P1–P6 + the two doctrines +
  the thinking loop + the confidence protocol; worked examples load most-relevant-
  first as space allows.
- Surface any clarifying questions to Brock before implementing, per your normal
  operating instructions.

## Acceptance for the whole change order

Done when all four "Done when" conditions above are met, the behavioral core is
provably loaded in full every session, and nothing in the existing V1-Lite scope or
doctrines has regressed.
