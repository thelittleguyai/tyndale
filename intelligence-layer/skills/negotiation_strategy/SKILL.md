---
name: negotiation_strategy
description: |
  Pick which appeal/negotiation framework applies to a specific case (ERISA internal
  appeal vs. ACA external review vs. NSA open negotiation vs. NSA IDR vs. state DOI
  complaint vs. direct provider negotiation vs. charity care vs. collections dispute)
  and sequence the next steps. Use this any time a case needs strategic direction on
  what to do next about a confirmed finding. Do NOT use it to detect errors (use
  bill_error_detection) or to draft letters (document_generation — Full V1). ALWAYS
  load 00_diagnostic_index.md first. In V1-Lite this Skill is DIAGNOSTIC-ONLY (see the
  mode note below).
version: 1.0.0
---

# Negotiation & Strategy Skill

> **mode: v1-lite-diagnostic-only** — In V1-Lite, this Skill provides ONLY the
> diagnostic index. The Lead Planner reads the diagnostic to identify the applicable
> framework, then recommends a **scripted action the user takes themselves** (V1-Lite
> defers letter generation). Full V1 builds out the 11 framework files under
> `frameworks/`.

This is the Strategist's playbook (in V1-Lite, the Lead Planner consults it directly). It
identifies which framework applies and sequences the steps.

## Two-layer architecture

1. **Diagnostic first.** ALWAYS load [`00_diagnostic_index.md`](00_diagnostic_index.md) and
   answer its questions to identify the applicable framework.
2. **Framework second.** In **Full V1**, load the matching file under `frameworks/` for the
   detailed step-by-step sequence, deadlines, and citations. In **V1-Lite**, `frameworks/` is
   intentionally empty (see `frameworks/README.md`) — the Lead Planner recommends a scripted
   action instead of loading a framework file.

## Operating rules

- [`intelligence-layer/reference/principles.md`](../../reference/principles.md) — **P5:
  default to action, not options.** Recommend a specific path, not a menu.
- [`intelligence-layer/reference/voice_tiering.md`](../../reference/voice_tiering.md) —
  recommendations are **Tier C** (reasoning, NEVER an outcome prediction).
- [`intelligence-layer/reference/citations.md`](../../reference/citations.md).

## The 11 frameworks (Full V1)

ERISA internal appeal · ACA external review · NSA open negotiation · NSA IDR · state DOI
complaint · state external review · Medicare appeals · Medicaid appeals · direct provider
negotiation · charity care application · collections dispute. The diagnostic maps a case to
one of these; the framework files themselves are Full V1 work.
