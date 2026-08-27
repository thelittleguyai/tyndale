# 37 · X-Rules Machine-Readable Contracts — DRAFT for Brock sign-off

**Status: DRAFT (Cowork, 2026-08-12).** X1 is Brock-authored and enforcing in CI. X2/X3/X5 below are drafted to the same contract shape for his approval — **the `error_type` taxonomy in X5 is a PROPOSAL derived from the existing check families and needs his authority.** X4/X6 are judge-scored (out of scope here, per D-A).

Contract shape (from X1): *what must be true · what fails · one worked failing example with named reasons.*

---

## X2 — surface-only-if-actionable

**Applies to:** every finding rendered to the user (thread, sub-case page, Record).

**MUST (one of):**
1. The finding carries **≥1 attached action**, where an action is a user-executable next step bound to that finding: a call step in the gameplan targeting it · a document request whose satisfaction advances it · a generated dispute/appeal artifact · an in-app confirm/decision the user can take now.
2. OR the finding is explicitly typed **`presentation: informational_context`** and renders under the context treatment (no action row, labeled as context — e.g., the §5.4 "not an error, here's the real math" reconciliation).

**FAILS when:** a finding renders with zero attached actions and no `informational_context` type. "An action exists somewhere else in the plan" does not pass — the binding must be finding→action, not page→actions.

**Worked failing example:**
> "Your insurer applied your deductible in an unusual order." *(no action attached, no context label)*
> → FAIL X2: reasons `no_attached_action`, `not_typed_informational`.

**Machine check:** for each rendered `finding_id`: `len(actions.filter(finding_id)) ≥ 1 OR finding.presentation == "informational_context"`.

---

## X3 — input-dependence honesty

**Applies to:** every user-facing computed figure (three numbers, per-finding impacts, cap/accumulator statuses, estimates).

**MUST:** if the figure's computation consumed an incomplete input set (`missing_inputs ≠ ∅` — the engine already tracks assumptions/missing inputs per DL-72/85), the rendered figure carries a **qualifier in the same visual unit** (same card/line — not a footnote elsewhere) that **names at least the single most material missing input specifically**:
- Qualifier shape: *"based on what I have — without your {missing_input} this is my best number"* or the range form *"between {low} and {high} until I see your {missing_input}"*.
- "Estimated" alone **fails** — the missing input must be named.
- Disclosure tiers (0–3) map: tier 0 → no qualifier permitted (inputs complete); tiers 1–3 → qualifier mandatory, escalating to the range form at tier ≥2.

**FAILS when:** a bare figure renders while `missing_inputs ≠ ∅`; or the qualifier is generic ("estimated", "approximate") without naming an input; or the qualifier is visually detached from the figure.

**Worked failing example:**
> "**What you should actually owe: $612.40**" *(rendered while the SBC is missing and deductible status is assumed)*
> → FAIL X3: reasons `missing_inputs_nonempty` (`sbc`), `no_qualifier_in_unit`.

**Machine check:** for each rendered figure node: `figure.missing_inputs == [] OR (figure.qualifier != null AND qualifier.names ⊇ {most_material(figure.missing_inputs)} AND qualifier.same_unit == true)`.

---

## X5 — name-the-specific-error

**Applies to:** every finding with `finding_class: error` (distinct from opportunities like charity-care and from informational context).

**MUST carry all three:**
1. **`error_type`** from the enum below — never null, never free text.
2. **≥1 implicated line item** (line-item refs into the case's extracted lines; a document-level error like balance billing may reference the bill-total line, but the ref must exist).
3. **Dollar impact** — a computed amount, a range (X3 rules then apply), or the explicit `impact_unknown` with a `reason` from: `awaiting_itemized_bill`, `awaiting_eob`, `awaiting_coverage_terms`. Silent absence fails.

**PROPOSED `error_type` enum** *(derived from the shipped check families + the B-series handoff — Brock: amend/rename/extend; this taxonomy is yours)*:
`duplicate_charge` · `upcoding` · `unbundling` · `units_exceeded` (MUE) · `phantom_service` (billed, didn't happen) · `balance_billing_violation` · `deductible_misapplied` · `cost_sharing_math_error` (coinsurance/copay arithmetic) · `preventive_cost_shared` · `noncovered_misapplied` (covered service processed as not covered) · `extreme_markup` (B4, uninsured/self-pay benchmark) · `cob_misordered` (B6, wrong primary/secondary order) · `stale_accumulator` (payer applied out-of-date deductible/OOP position) · `other_billing_error` *(escape hatch — permitted ONLY with a named sub-label; candidates for promotion into the enum reviewed monthly from analytics)*

**FAILS when:** `error_type` null/free-text · zero line-item refs · impact absent without a typed reason.

> **Mapping note (2026-08-22, the §3 `error_detection_rules` extension — one taxonomy, two enums, NOT merged):**
> *(2026-08-27 note: this rule_type→error_type mapping is DOCUMENTED-NOT-YET-WIRED — the
> code lands after your sign-off. The enums live in `runtime/app/knowledge/rule_schema.py`
> + the collection JSON schema `intelligence-layer/collections/schemas/error_detection_rules.json`
> — not collections.py.)*
>
> the collection's new payer-side `rule_type`s feed these `error_type`s when a rule produces a finding:
> `deductible_misapplication` → `deductible_misapplied` · `oop_max_ignored` → `stale_accumulator` ·
> `coinsurance_rate_error` → `cost_sharing_math_error` · `cob_misordering` → `cob_misordered` ·
> (`aca_preventive`, now rule_class `legal_protection`) → `preventive_cost_shared`.
> **Three payer rule_types have NO error_type today** — `network_status_misapplied`,
> `auth_on_file_ignored`, `allowed_amount_above_contract` — they route through
> `other_billing_error` + sub-label until you either extend this enum or rename; your call
> (flagged in the 2026-08-22 debrief). `extreme_markup` deliberately does NOT map to
> `allowed_amount_above_contract` — one is a self-pay benchmark claim (B4), the other a
> contract-adjudication error.

**Worked failing example:**
> "Something looks wrong with the charges on this bill — worth asking your provider about."
> → FAIL X5: reasons `error_type_missing`, `no_line_item_ref`, `impact_missing_untyped`. *(Also fails X2.)*

**Machine check:** `finding.error_type ∈ ENUM AND len(finding.line_item_refs) ≥ 1 AND (finding.impact != null OR finding.impact_unknown_reason ∈ REASONS)`.

---

## Open for Brock (blocking sign-off)
1. **The X5 enum** — approve/amend; especially whether `other_billing_error` may exist at all, and the promotion process for new types.
2. X2: does the §5.4 rung-0 reconciliation ("not an error, here's the real math") satisfy as `informational_context`, or does explaining-the-difference itself count as the action?
3. X3: confirm the tier→qualifier mapping (tier ≥2 forces the range form) matches the locked disclosure-ladder intent.
