"""Real Anthropic Claude agent orchestration for the V1-Lite Lead Planner +
Bill Detective + Math Person trio.

Public entrypoint:  ``app.agents.orchestrator.run_audit(case_file_id)`` →
``AuditResult``.

Module map:
  * ``context_loader``  — filesystem reads of ``intelligence-layer/`` assets
                          (behavioral_core, subagent prompts, Skills).
  * ``runner``          — shared Claude tool_use loop wrapper.
  * ``bill_detective``  — BD subagent (provider-side / encounter-mismatch findings).
  * ``math_person``     — MP subagent (three-number independent audit).
  * ``lead_planner``    — composer (final user-facing answer).
  * ``orchestrator``    — sequences the three agents per V1-Lite effort scaling.
"""
