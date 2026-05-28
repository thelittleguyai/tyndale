# Wrongful denial (PAYER-SIDE)

**What this is.** A service was denied in a way inconsistent with the plan terms or
governing law. A denial is the insurer's CLAIM that nothing is owed by them — it is audited,
not assumed valid. The detection signal is a GAP between the denial rationale and the plan
terms / law.

**Detection signals.**
- A denial reason that contradicts the SBC or covered-benefit list.
- "Not medically necessary" denial against an applicable coverage policy or guideline.
- A denial that ignores a legal protection (preventive, NSA, parity, emergency).

**Citation language.** Tier B: "The denial is inconsistent with the plan's coverage of
[service] and/or with [ACA §2713 / NSA §300gg-111 / MHPAEA §1185a as applicable, src_TBD]."

**Severity.** High — full denials are the largest dollar exposures.

**Common defenses.** Insurer cites medical-necessity or policy. Response: cite the specific
coverage policy / payer_policies chunk and the clinical facts.

**Required evidence.** The denial/EOB, SBC, the relevant payer policy, and clinical records.

**Recommended remediation (Tier C).** File an internal appeal; if exhausted, external
review. Sequence via `negotiation_strategy` (`erisa_internal_appeal`, `aca_external_review`).
