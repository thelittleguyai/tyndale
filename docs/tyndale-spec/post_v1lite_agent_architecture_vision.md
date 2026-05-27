# Post-V1-Lite Vision — The Broader Agent Architecture (PARKED — do not build yet)

**To:** Claude Cowork (Tyndale build PM/product manager)
**From:** Brock
**Status:** PARKED / FUTURE. Do **not** build any of this during V1-Lite or as part
of Change Order 001. This document exists so the larger vision is remembered and can
be incorporated **after** V1-Lite ships and stabilizes. Treat it as a backlog /
north-star, not a work order.

---

## Why this is parked

V1-Lite is deliberately lean: the user-facing intelligence layer (Lead Planner +
Bill Detective + Math Person), the knowledge collections, the PHI spine, the
feedback loop, and a mobile-friendly web app. The architecture below is a much
larger build — an internal "AI agent company" that runs and improves the business.
Building it now would blow the V1-Lite scope and timeline. But several pieces are
genuinely valuable later, so they're captured here rather than lost.

When V1-Lite is live and stable, revisit this document and decide — with Brock —
which pieces to pull into the roadmap and in what order.

---

## The concept: Tyndale as a small "AI agent company"

The original expanded vision framed Tyndale not as one agent but as a coordinated
company of agents: one user-facing agent the customer talks to, and many agents
behind it that keep the product running, support the business, and drive continuous
improvement. Agents are tiered by blast radius, data access, and human-in-the-loop
cadence, and they coordinate through a central Orchestrator rather than calling each
other directly.

**Important reconciliation note for Cowork.** The current Tyndale build uses the
Claude Agent SDK with a Lead Planner orchestrating subagents — that pattern already
covers the *user-facing* coordination this vision describes. So when this vision is
revisited, do NOT treat it as a rewrite. The user-facing layer stays as built; this
vision mostly adds **operational, strategic, and meta agents around it.** Reconcile
"Orchestrator" terminology with the existing Lead Planner / Agent-SDK architecture
rather than introducing a competing orchestrator for user-facing work.

---

## The tiers (future reference)

- **T1 — User-facing.** The agent the user talks to. ALREADY BUILT in V1-Lite (Lead
  Planner + subagents). No change needed from this vision.
- **T2 — Subject-matter experts (read-only specialists).** A Medical Billing Expert,
  a Health Insurance Expert, and an internal company-side Legal Agent, callable on
  demand for depth. (Note: V1-Lite already has Bill Detective and Math Person; the
  full build has Legal Researcher and Strategist. This tier overlaps — reconcile
  rather than duplicate.)
- **T3 — Operational.** Keep the product running: a Bug Hunter (tests + fixes), a UX
  Quality agent (watches transcripts/telemetry for friction), a Security agent
  (dependency/secret/config scanning), an Integrations agent (scopes new vendors).
- **T4 — Strategic.** Help run the business: Strategy, Data Scientist, NLP Analytics
  (natural-language querying of metrics, scoped per-user or admin), Financial Ops
  (unit economics, per-user API cost, LTV/MRR), Content/Marketing, Customer Success.
- **T5 — Autonomous / scheduled.** Cron-driven: Proactive Monitor (deadlines/follow-
  ups — note V1-Lite already has a proactive monitor concept), Regulation Researcher
  (keeps the laws/regulations collection current — also already in the current
  build), Compliance Scanner.
- **T6 — Meta / coordination.** The Orchestrator and a QA agent that police and
  coordinate the other tiers.

---

## The pieces most worth pulling forward first (Brock's prior lean)

From the original vision, two pieces raise the safety/quality floor the most and are
the strongest early candidates once V1-Lite is stable:

1. **A QA agent** that reviews a sampled percentage of user-facing outputs in real
   time before they reach the user — flagging overconfidence, missing citations,
   scope violations (medical/legal-advice leakage), tone mismatches, or unsupported
   claims, and holding low-confidence responses for review. This overlaps with the
   current build's citation enforcement and code-validator layers; when revisited,
   extend those rather than building a parallel system. The useful new idea is
   **sampled real-time review with a hold-for-approval gate**, tunable from 100%
   sampling early down to 10–20% as trust builds.

2. **A Compliance Scanner** (scheduled) once the full HIPAA/Full-V1 surface exists —
   continuous config/compliance auditing. Pairs with the HIPAA compliance engineer's
   work.

The rest (Strategy, Financial Ops, Content/Marketing, etc.) are valuable business-
operations tooling but are not on the critical path to a great user-facing product.

---

## Coordination & governance ideas worth keeping (for whenever this is built)

- **An Orchestrator coordination log** — a durable record of every non-trivial agent
  proposal, decision, and execution, with risk level and human-approval status, so
  Brock has one place to see what the agent company is doing.
- **Hard human-in-the-loop gates** — every outbound communication, every behavioral-
  spec change, every schema change, every deployment, and every legal-risk-tagged
  item requires explicit Brock approval with an audit trail. (Consistent with the
  current build's posture — never send/publish without approval.)
- **Scoped data access by tier** — subject-matter agents never touch raw user PII;
  analytics queries are row-level-scoped to the requesting user unless admin; the
  tool executor enforces an allowlist per agent and raises a scope violation on any
  attempt to step outside. This is a strong governance pattern to carry forward.
- **Prefer cheaper models for high-volume ops work** — routine ops/log-scanning on a
  cheap model; reasoning-heavy work (user chat, legal, strategy) on the stronger
  models. (Consistent with current model-routing discipline.)

---

## What to do with this document now

- **Nothing to build.** Hold it as backlog/north-star.
- When V1-Lite is live and stable, raise it with Brock and propose which pieces (QA
  agent and Compliance Scanner are the likely first picks) to pull into the roadmap.
- When revisited, reconcile all terminology and roles with what V1-Lite/Full V1
  actually built — extend the existing Agent-SDK + Lead Planner architecture; do not
  introduce a competing orchestrator or duplicate the existing subagents.
- Keep every future addition behind the same human-in-the-loop and scoped-access
  governance the current build already follows.

*Source: an earlier "Agent Architecture & Expanded Roster" concept for Tyndale,
preserved here so the larger vision survives the lean V1-Lite launch.*
