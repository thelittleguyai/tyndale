# Task L01 — V1-Lite orientation & file markers

**Phase:** L1 · V1-Lite foundations
**Who:** Brock + Claude Code
**Estimated time:** 20 minutes
**Depends on:** Full Build Kit Tasks 01–07 done (the repo exists with foundation files)

## What this task does

Sets up the conventions that let V1-Lite files coexist cleanly with full-Tyndale files in the same repository, so that when you later expand to full Tyndale nothing conflicts and it's always clear which mode a file belongs to.

## Prompt to paste into Claude Code

```
We're building Tyndale V1-Lite — a leaner first version that ships before
the full intelligence layer. It lives in the SAME repository as the full
build. I need to set up conventions so V1-Lite and full-version files
coexist cleanly.

Context (read these first if present):
- v1_lite/01_v1lite_scope_and_compatibility.html (the V1-Lite scope spec)
- reference/discipline_rules.md
- CLAUDE.md

Please do the following:

1. Update CLAUDE.md to add a "V1-Lite vs Full" section explaining:
   - V1-Lite is the leaner first version: document upload instead of FHIR,
     3 agents (Lead Planner + Bill Detective + Math Person) instead of 6,
     no letter generation yet, plus a feedback loop from day one.
   - V1-Lite shares ALL contracts with full Tyndale (case file schema,
     citation format, voice tiering, Skill structure, tool signatures).
   - Files that are V1-Lite-specific carry a `mode: v1-lite` marker in
     their frontmatter or a header comment.
   - Files shared by both versions carry no mode marker (they're universal).
   - The upgrade path is expansion, not rewrite: V1-Lite components get
     promoted/extended, not replaced.

2. Create a top-level `MODES.md` file documenting the convention:
   - `mode: universal` (default, no marker needed) — shared by both
   - `mode: v1-lite` — only used in the lean version
   - `mode: full-only` — deferred until the full upgrade
   And a table listing which existing files are which:
     * reference/* → universal
     * skills/bill_error_detection → universal
     * skills/cost_estimation → universal
     * skills/coverage_connection_fhir → universal (but has v1-lite manual mode + full-only FHIR mode sections)
     * skills/find_a_doctor, skills/plan_a_visit → universal (optional in v1-lite)
     * skills/document_generation → full-only
     * skills/negotiation_strategy → full-only (guidance folded into Lead Planner for v1-lite)
     * skills/charity_care_eligibility → full-only
     * subagents/lead_planner → has both a v1-lite collapsed prompt and the full prompt
     * subagents/bill_detective, subagents/math_person → universal
     * subagents/legal_researcher, subagents/strategist, subagents/code_validator → full-only
     * tools/descriptions/fhir_* → full-only
     * tools/descriptions/upload_extract_* → v1-lite (new; matches FHIR return shapes)
     * collections/* → universal
     * evals/* → universal

3. Create the directory `subagents/lead_planner/v1_lite/` where the
   collapsed V1-Lite Lead Planner prompt will live (Task L04 fills it).
   The existing subagents/lead_planner/system_prompt.md remains the FULL
   version prompt.

4. Create the directory `tools/descriptions/v1_lite/` where the
   upload-extraction tool descriptions will live (Task L02 fills it).

5. Create the directory `feedback/` for the feedback loop components
   (Tasks L05, L06 fill it).

Commit with message "V1-Lite orientation: modes convention and directory scaffolding".
```

## Done when

- `CLAUDE.md` has the V1-Lite vs Full section
- `MODES.md` exists with the mode table
- The three new directories exist
- Git log shows the commit

## Next task

[Task L02 — Document upload & extraction tools](L02_upload_extraction_tools.md)
