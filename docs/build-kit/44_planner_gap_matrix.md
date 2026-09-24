# 44 · Planner gap matrix — does the intake ask for everything the math needs?

**Status:** engineering audit, 2026-09-24 (guided Phase 2, item H), for Brock's review.
**Audited:** `runtime/app/intake/planner.py` (the gap list and the screen registry), against
`docs/research/tyndale_oop_calculation_method.md` Part 1, groups A–E: the inputs the independent
"Tyndale-computed" figure rests on.
**Guard:** `runtime/tests/test_planner_gap_matrix.py` parses the table below. CI fails in four
cases:
- a planner gap is missing from this table;
- the table names a gap or screen the planner does not have;
- a row's screen disagrees with the code;
- a Part 1 input loses its row.

## How to read it

The planner never re-implements a signal. For each input it reads the seam that owns it (the
extraction, the priors, the accumulator engine). The **how** column is the planner's existing
Tier 0–3 ladder (planner docstring, "SILENT vs ASK"):

| how | meaning | tier |
|---|---|---|
| **inferred** | read off a document the member already gave — never asked | 0 |
| **asked** | a screen asks when no document settles it AND the input is load-bearing (its plausible spread crosses the USER_CHASE bar) — "I'm not sure" is always an answer | 3 — the chase |
| **silent** | the audit defaults it below the chase bar and records the assumption; no screen | 0–1 |
| **not captured** | no seam reads it today — neither asked nor defaulted on purpose | — |

"inferred → asked" means the planner reads it off a document first and asks only when the
document did not say.

## The matrix

| id | input (OOP method Part 1) | how | gap key | screen | where it comes from / what happens without it |
|---|---|---|---|---|---|
| A1 | Procedure codes (CPT/HCPCS) | inferred → asked | `bill`, `itemized_bill` | bill, bill_itemized | Read off the itemized bill by the engine (Bill Detective, translate pass). A summary bill has no codes: the planner coaches the itemized request, never proceeds silently. Skipping it leaves "This bill shows totals only." |
| A2 | Diagnosis codes (ICD-10) | not captured | — | — | No seam extracts them. They are not a planner ask (nobody should be asked for codes). **Engine follow-up:** read them off the claim form / EOB where printed. |
| A3 | Date of service | inferred | — | bill_summary | Read off the bill (`case_files.date_of_service`) and read back on bill_summary, where "fix" re-opens capture. It orders the timeline and places the visit in its plan year. |
| A4 | Place of service | not captured | — | — | No seam extracts it. **Engine follow-up.** |
| A5 | Rendering provider + NPI | inferred (name); NPI not captured | — | bill_summary | The name is read off the bill and read back. No seam extracts the NPI; only the Medicare participation lookup uses NPIs. |
| A6 | Network status (in / out) | inferred, else silent — **new gap** | `network_status` | eob | Read off the EOB's in/out-of-network line at upload (`documents[].network`); THIS visit's EOB wins, and any "out" wins. With no line, the cost-share model runs its in-network arithmetic, i.e. it **assumes in-network**. Until now nothing said so. The readiness screen now does: "No paper says if this doctor is in your plan's network. I assumed they are." Never asked: members rarely know, and no out-of-network arithmetic exists for an answer to feed. |
| A7 | Billed charge | inferred | `bill` | bill | Line-item charges off the bill, else the EOB's billed figure. |
| A8 | Allowed amount — the cost-share basis | inferred, else silent — **new gap** | `allowed_amount` | eob | Only an EOB states it (the rung-2 anchor `"allowed"`). Without one, the audit's figure runs on the **billed** charge (anchor `"billed"`), an upper bound. Until now the readiness screen did not say so; it now does: "I used the billed price, so your real share may be lower." It is chased through the EOB ask, so skipping the EOB skips it. An EOB whose allowed amount the read cannot find leaves it unresolved without asking again. |
| A9 | Which insurer (not in Part 1: the plan lookup's key) | inferred → asked | `payer` | card, insurer | Card, bill or EOB first. Otherwise the insurer ask. The BCBS router (item G) refines it for "Where to find it" only. |
| A10 | The payer's statement itself | inferred → asked | `eob` | eob | The EOB ask. Skipping it: "No EOB. I can't check your insurer's math." |
| B1 | Deductible — individual | inferred → asked | `plan_rules` | plan_rules | SBC (on the case or at plan level), the card, or the Plan Library's copy (confirmed on plan_rules_confirm). Missing, it is swept over the researched prior. Its span crosses USER_CHASE, so the SBC is asked for. |
| B2 | Deductible — family; embedded vs aggregate | inferred (family amount); structure silent | — | — | The SBC read captures `deductible_family`. **Embedded vs aggregate is not captured.** The accumulator engine records the assumption "individual in-network single bucket". **Open for Brock** (the method calls a wrong call here "common, expensive"). |
| B3 | Coinsurance rate | inferred → asked | `plan_rules` | plan_rules | `coinsurance_percent`, a required cost-share input, swept over its prior when missing. It rides the SBC ask: a fraction is not chase-sized alone. |
| B4 | Service-specific copays | inferred; silent in the math | — | — | `copay_pcp` / `copay_specialist` come off the SBC. The rung-2 model has no copay arithmetic (its range absorbs copays). Whether a copay applies before the deductible is not captured. |
| B5 | Out-of-pocket max — individual | inferred → asked | `plan_rules` | plan_rules | `oop_max_amount`, required. A stated cap bounds every evaluation. |
| B6 | Out-of-pocket max — family (embedded) | inferred; silent in the math | — | — | `oop_max_family` comes off the SBC but the model does not use it. The ACA embedded individual cap (Part 3) is not enforced at intake. |
| B7 | Separate in/out-of-network deductible / OOP | inferred (checklist keys); silent | — | — | `deductible_out_of_network` / `oop_max_out_of_network` exist as coverage keys (manual entry, Plan Library). The model is in-network only (see A6). |
| B8 | Per-service treatment (deductible / copay-only / preventive $0 / non-covered) | silent | — | — | Not captured. Every line gets deductible-then-coinsurance. The preventive $0 rule lives in the rules layer, not the planner. **Open for Brock.** |
| B9 | Grandfathered status | inferred; silent | `coverage_type` | coverage_type | Persisted when regime detection finds it (`coverage_attributes`). Never asked: the method itself says it is "handled silently". |
| C1 | Deductible already met | inferred → asked | `deductible_met` | deductible_met | The confirmed EOB stack answers it (CO-12B reconstruction, authoritative per DL-72); then the manual ask never appears. Otherwise it is asked only when load-bearing (the deductible's span crosses USER_CHASE). |
| C2 | Out-of-pocket already met | inferred → asked | `oop_max_met` | oop_met | Same rule as C1, against the OOP max. |
| C3 | Accumulators per individual / family and per network | inferred (EOB buckets); silent otherwise | `eob_completeness` | timeline | The reconstruction buckets in / out / unknown network, and counts family members when their EOBs are on the case. The manual asks take ONE number (assumed individual, in-network). |
| C4 | The EOB stack is complete | asked, every time | `eob_completeness` | timeline | Locked 5d: asked again whenever the stack changes. |
| D1 | Which person the claim is for | asked when it differs | `attestation` | attest | Attest-and-proceed when the patient is not the account holder (existing machinery). The timeline tracks whose EOB each row is. |
| D2 | Secondary insurance / COB | asked (not load-bearing) | `other_insurance` | other_insurance | Checked, never assumed to cover the rest. |
| D3 | Plan-year boundaries | inferred → asked | `plan_year_start` | plan_year | The SBC's coverage period first, then the ask. Never assumed January 1. Persisted on the case (item E). |
| D4 | State | inferred; silent | — | — | `case_jurisdiction`: the document's patient state wins, then the profile's (Settings). Unknown otherwise, and the audit states that assumption. Not a planner ask. |
| D5 | Kind of coverage (not in Part 1: it gates the route) | inferred → asked | `coverage_type` | coverage_type | Verified regime detection, else the plain-language ask. Phase 1 carries commercial only. |
| E1 | What was actually received (the reality check) | asked | `encounter_facts` | confirmations | One card per fact the engine could not settle from paper. Never capped, never padded, never asked twice (fact identity, round 3). |

## What item H changed

The gap list now carries the two dimensions the audit found missing, both in the claim group:

- **`allowed_amount`**: resolved when an EOB states the allowed amount. It is read by the same
  seam the audit's figure anchors on (`extraction.eob_money_figures`).
- **`network_status`**: resolved when an EOB says in or out of network. It is marked not
  load-bearing: no prior spans it, and the model has no out-of-network arithmetic.

Neither adds a screen. Both point their readiness "Change" link at the EOB capture, the one
place the answer can come from, and each has its readiness label and limit line (PROPOSED in
the v2 DRAFT).

## Open for Brock: what the math cannot see yet

These rows are silent or not captured. None of them is a planner question. Each is either an
engine read that does not exist yet, or a plan-design fact the SBC read does not keep:

1. **B2: embedded vs aggregate family deductible.** It is the method's own "common, expensive
   error". Today every case is treated as an individual single bucket, and that is recorded.
2. **B8: per-service treatment**, especially preventive $0 and copay-only services.
3. **A6 / B7: out-of-network arithmetic.** The engine assumes in-network. A known "out" is now
   visible on readiness but is not yet priced differently.
4. **B6: the ACA embedded individual OOP cap** on family plans.
5. **A2 / A4 / A5: diagnosis codes, place of service, NPI.** These are engine extraction work,
   never member questions.
