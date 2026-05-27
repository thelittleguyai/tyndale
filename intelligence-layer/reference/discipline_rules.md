# Tyndale Discipline Rules

This file consolidates every operational discipline rule across the 22 architectural decisions
that define Tyndale's intelligence layer. Use this as a reference; the rules themselves are also
embedded in the relevant Skill, subagent, and tool description files.

## How to use this reference

Engineers (Phil, Jonas, Josh) and authors (Brock) can search this file for a specific rule —
e.g., "what was the rule about prompt caching tier boundaries?" — and find it under the relevant
decision area below. Each rule is also embedded in the Skill, subagent, or tool description file
where it applies; this file is the consolidated, canonical copy. When the embedded copy and this
file disagree, fix both — they should never diverge.

## D0 — The Independent Audit Doctrine (foundational, ranks above all)

(6 rules)
1. Neither the provider's bill nor the insurer's EOB is a source of truth. Both are CLAIMS by
   parties whose work Tyndale audits.
2. Tyndale computes what SHOULD be true independently — from the user's actual coverage terms,
   the codes, the rules, and the law — BEFORE looking at what the EOB claims, so the EOB cannot
   anchor the result.
3. Three numbers are always reported: what the provider billed, what the payer's EOB claims the
   member owes, and what Tyndale independently computes the member should owe. A gap between
   Tyndale's figure and the EOB is a payer-side finding; a gap with the bill is a provider-side
   finding. Both are pursued with equal rigor.
4. Payer-side error categories (cost-sharing miscalculation, coverage misapplied, wrongful
   denial, network-status error, OOP-max ignored) get equal weight to provider-side categories
   in detection.
5. Before a charged service is treated as legitimate, the encounter is verified: against
   clinical data (full Tyndale) or by translating each line item to plain language and having
   the user confirm it matches their visit (V1-Lite). A mismatch is a candidate phantom-charge
   or upcoding finding.
6. Encounter verification asks the user to confirm FACTS about their visit, never to make a
   CLINICAL JUDGMENT (the latter is out of scope per the refusals). In V1-Lite, every user
   confirmation is captured as a label that validates full Tyndale's automated encounter
   verification.

## D0b — The Grounding & Graceful Degradation Doctrine (foundational)

(6 rules)
1. Every factual, legal, coverage, or pricing assertion is grounded in an authoritative source —
   a retrieved chunk, a structured table, the user's own documents, or a computation over those.
   The model's training-data recall is NEVER the basis for an assertion. (This is what makes
   Tyndale superior to a general LLM for billing, the way a data-grounded clinical tool beats a
   general model at diagnosis.)
2. Every capability names its grounding source: codes → billing_codes + catalogs;
   bundling/limits → NCCI/MUE structured tables; error rules → error_detection_rules; law →
   laws_regulations (point-in-time filtered); payer rules → payer_policies (version-stamped);
   coverage math → user's actual coverage terms; pricing → FAIR Health + Medicare RVU + hospital
   transparency; providers → NPI registry + payer directories + CMS Care Compare.
3. Tyndale reaches for the MOST authoritative and MOST specific source available (structured over
   narrative for code rules; statute over summary for law; the user's actual plan over a generic
   assumption; payer-specific over generic).
4. Tyndale is transparent about which source backs each claim, and when it must use a weaker
   substitute, it says so explicitly ("I'm using the Medicare benchmark because I don't have your
   commercial rate").
5. Incomplete data narrows the answer; it never dead-ends the user. Tyndale does the most it can
   with what it has, states what it can't yet conclude, helps the user get the missing piece
   (with scripts per P1), and always delivers some real value rather than refusing until inputs
   are complete. (The degradation ladder: full → partial → minimal data, each rung showing value.)
6. When the user can't find their coverage info, helping them find it is PART OF THE JOB Tyndale
   does — not a prerequisite the user must satisfy alone.

## D2 — Subagents

(2 rules)
1. Every subagent has a dedicated system prompt versioned in git.
2. Subagent prompts reference foundation files (principles, voice tiering, refusals, citations,
   glossary) by inclusion, not by repetition.

## D3 — Model assignments

(3 rules)
1. Model versions pinned to dated IDs. No floating aliases.
2. Lead Planner = Sonnet 4.6; Strategist = Opus 4.7; Code Validator = Haiku 4.5; all other
   subagents and Skills = Sonnet 4.6.
3. Judge model = Opus 4.7. Never sees the same prompt that generated the output being judged.

## D4 — Skills

(7 rules)
1. Every Skill description is "a little pushy" with positive triggers, domain keywords, and
   exclusion clauses.
2. Every SKILL.md body stays under ~500 lines.
3. Reference files are one level deep from SKILL.md.
4. Imperatives reframed as "rule + reason."
5. In-skill examples of past appeal letters by type pre-filled in Document Generation reference
   files.
6. Skills versioned with semver in YAML frontmatter, shipped via git PR.
7. Any Skill requiring diagnosis before remediation includes a 00_diagnostic_index.md loaded
   first. Applies to: bill_error_detection, negotiation_strategy, charity_care_eligibility.

## D5 — Knowledge collections

(2 rules)
1. No behavioral rules in collections. Collections hold facts.
2. Mandatory point-in-time filters on laws_regulations and payer_policies.

## D6 — Embeddings

(3 rules)
1. Josh runs pre-launch NDCG benchmark of voyage-context-3 vs voyage-3-large on laws_regulations.
2. No mid-flight embedding model changes without re-embedding full collection.
3. Embedding model and dimension locked in collection metadata.

## D7 — Reranking

(4 rules)
1. All RAG queries go through rerank. No exceptions.
2. Instruction-following used aggressively (per-collection defaults).
3. Top-K from embedding search = 50; top-K returned from rerank = 5–10.
4. Rerank scores persisted in audit log.

## D8 — Hybrid search & chunking

(6 rules)
1. Hybrid search (vector + BM25 with RRF) on all 4 collections.
2. NCCI edits and MUE limits in structured Postgres tables, not Qdrant.
3. Section headings included inline at chunk top for laws_regulations.
4. Every payer_policies and laws_regulations chunk has effective_date_start and
   effective_date_end. Every query filters by date-of-service.
5. Chunk boundaries respect document structure (section breaks, not fixed token windows).
6. Chunk metadata schema versioned alongside collection.

## D9 — Vector DB

(5 rules)
1. Self-hosted Qdrant on Azure Container Apps in same VPC as FastAPI. No public ingress.
2. Quarterly Qdrant version upgrades in low-traffic windows.
3. Daily snapshots to Azure Blob with 30-day retention. Restore drills twice per year.
4. Performance targets: p95 search latency <50ms; recall@10 ≥0.95.
5. No Qdrant Cloud migration until formal HIPAA attestation.

## D10 — Crons

(5 rules)
1. Crons wrap stateless query() calls, not persistent agent sessions.
2. Idempotency by design.
3. Cron runs logged to the same audit stream.
4. Failure alerts route to ops, not users.
5. Cost budgets per cron with daily/weekly ceiling.

## D11 — Tool architecture

(7 rules)
1. In-process tools for PHI-touching and performance-critical paths.
2. allowed_tools allow-list scoped per subagent.
3. Tool descriptions get pre-V1 deliberate review pass.
4. PreToolUse hooks gate high-risk tools (send_email, public-facing writes).
5. Every tool call logged to audit stream.
6. Tools chain inside a single subagent invocation when possible (P6).
7. External MCP deferred to V1.1.

## D12 — Context management

(6 rules)
1. Subagent return payloads to Lead Planner are minimal (pointers).
2. Lead Planner writes plan to case file before complex work. Plan includes anticipated next
   steps.
3. Effort scaling explicit in Lead Planner prompt.
4. Context budget: <80K tokens per subagent invocation, hard ceiling 130K.
5. Citation chains preserved across compaction.
6. No subagent operates on stale plans.

## D13 — Citation enforcement

(7 rules)
1. Every generated legal claim has a citation.
2. Citation format consistent and machine-parseable.
3. Every retrieved chunk carries a source ID.
4. Layer 2 is a hard ship gate. Output fails Layer 2 = output does not ship.
5. Manual human review (Brock) of every generated appeal letter at V1.
6. Regulation Researcher cron writes last_verified_date to chunks.
7. Anthropic's Citations feature used where possible.

## D14 — Voice tiering

(6 rules)
1. Tier A facts come from structured inputs only.
2. Tier B claims use standard qualifiers and always cite.
3. Tier C recommendations include reasoning, not just instructions.
4. Forbidden: outcome predictions.
5. Skill and subagent prompts enforce tier rules.
6. Genuine uncertainty named specifically.

## D15 — Out-of-scope handling

(8 rules)
1. Five categories, clean decline. No routing for any of them.
2. Crisis detection classifier screens chat input.
3. Refusals route energy back to in-scope work, not to other resources.
4. One permanent footer disclaimer.
5. Contextual modal only on declined queries.
6. No per-message disclaimers on routine output.
7. Refusal correctness eval'd at ≥98%.
8. Decline language emphasizes scope ("I handle X"), not just refusal.

## D16 — Model routing

(8 rules)
1. LiteLLM self-hosted inside Azure VPC.
2. Claude-only fallback for clinical, legal, and user-facing reasoning paths.
3. Cross-provider fallback acceptable only for non-user-facing utility.
4. Maintenance-mode message on full fallback exhaustion. Postgres queue.
5. Model versions pinned to dated IDs. Upgrades via eval-gated PR.
6. Prompt caching enforced by default.
7. Quarterly silent-invalidator audit.
8. LiteLLM proxy is critical credential broker (hardened, weekly key rotation).

## D17 — Prompt caching

(10 rules)
1. Two-tier caching: 1-hour stable; 5-min session-stable; dynamic uncached.
2. Prompt structure enforced by LiteLLM proxy.
3. Silent invalidator audit quarterly.
4. Cache tier boundaries annotated in every prompt template; CI fails if dynamic content in
   1-hour blocks.
5. Cache hit rate targets per stage (40/60/75/85/90).
6. No caching of PHI-rich content beyond strict minimum.
7. Workspace-level cache isolation (production ≠ staging).
8. Tool definition changes batched.
9. Skill/system-prompt edits batched.
10. Cache warming after deploy.

## D18 — PHI scrubbing & logging

(10 rules)
1. Dual-stream logging architecture.
2. Microsoft Presidio with custom recognizers in PreToolUse hook.
3. Pre-V1 scrubbing benchmark required (≥98% direct ID recall; ≥90% context-dependent; ≥95%
   precision).
4. Audit log captures full provenance for every model output.
5. Field-level AES-GCM encryption; 90-day key rotation in Key Vault.
6. 7-year audit log retention.
7. No standing audit-log access. Per-investigation workflow.
8. Braintrust receives synthetic data only at V1.
9. Prompt injection defense via UserPromptSubmit hook.
10. Audit-log accesses themselves audited.

## D19 — BAA chain

(12 rules)
1. Anthropic HIPAA-ready Enterprise BAA signed directly + Azure BAA.
2. AWS Bedrock BAA signed.
3. No PHI flows to any vendor before BAA executed.
4. Voyage AI BAA confirmed in writing before user-bill embedding.
5. FAIR Health BAA confirmed in writing before full-ZIP queries.
6. BAA registry maintained.
7. Subprocessor change notifications reviewed within 30 days.
8. Annual BAA re-paper.
9. Braintrust synthetic-only at V1.
10. Cross-provider fallback only on non-user-facing utility.
11. Stripe BAA signed defense-in-depth.
12. Observability vendor BAA signed defense-in-depth.

## D20 — Evaluation platform

(10 rules)
1. Braintrust as primary platform with CI/CD.
2. Arize Phoenix as production trace exporter.
3. Three eval contexts: PR smoke (~40 cases), nightly full (~600), V1.1+ production replay.
4. Eval suite structured by what it tests (per-Skill, per-subagent, voice/safety).
5. LLM judge is Opus 4.7. Different generation than the original output.
6. Judge calibrated against human golden set. Cohen's κ ≥ 0.6.
7. Per-PR smoke evals complete in <5 minutes.
8. Nightly regressions trigger Slack alerts to #tyndale-evals.
9. All eval data synthetic at V1.
10. Cost ceiling per eval run: $25/night, $1/PR.

## D21 — Ship gates

(10 rules)
1. Three layers of test data (golden, synthetic adversarial, production replay).
2. Seven ship gates run on every PR. Regression blocks deploy.
3. Citation faithfulness ≥99.5%; hallucination ≤1.0%; factual accuracy ≥99%.
4. Refusal correctness ≥98%.
5. Voice tier compliance composite (mean ≥4.0/5, no item below 3.0).
6. End-to-end latency gates (p50 <8s, p95 <25s).
7. Baseline updates require second approver.
8. All eval data synthetic at V1.
9. Pre-launch readiness check is real (not pro-forma).
10. Eval suite grows from production findings.

## D22 — Failure mode instrumentation

(8 rules)
1. Seven failure modes explicitly instrumented.
2. Each failure mode has alert threshold and routing channel.
3. Audit log captures everything needed for investigation.
4. Weekly alert review by Brock.
5. Quarterly failure-mode review.
6. PHI cross-session leakage detection, Skill execution sandbox, race condition detection
   deferred to V1.1+.
7. Severe alerts page Brock immediately.
8. Synthetic equivalent generated for any production failure; added to eval suite.
