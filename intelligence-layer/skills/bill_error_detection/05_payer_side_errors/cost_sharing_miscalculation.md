# Cost-sharing miscalculation (PAYER-SIDE)

**What this is.** The insurer's "member responsibility" on the EOB is wrong. The EOB is the
insurer's CLAIM about what you owe — not the truth. The detection signal is a GAP between
that claimed figure and Tyndale's independent computation from the coverage terms.

**Detection signals.**
- Tyndale computes (deductible remaining → coinsurance → OOP cap) a different member
  responsibility than the EOB states.
- Coinsurance applied to the full charge instead of the allowed amount.
- Deductible and coinsurance both applied to the same dollars (double counting).
- The ordinary person never catches this because they assume the insurer did the math right.

**Citation language.** Tier B against plan terms: "Member cost-sharing computed from the
plan's accumulators and benefit design is $X; the EOB's $Y is inconsistent with the SBC
[plan SBC / summary plan description, src_TBD]."

**Severity.** High — directly overcharges the patient; very common.

**Common defenses.** Insurer cites internal processing. Response: present the three-number
breakdown and the coverage terms used.

**Required evidence.** EOB, SBC, deductible/OOP amounts-met, and the allowed amount.

**Recommended remediation (Tier C).** Request reprocessing with Tyndale's computation
attached; escalate via `negotiation_strategy`.
