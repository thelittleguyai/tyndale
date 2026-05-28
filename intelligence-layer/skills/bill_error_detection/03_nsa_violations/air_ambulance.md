# Air-ambulance balance bills (No Surprises Act)

**What this is.** An out-of-network air-ambulance provider balance-bills the patient above
in-network cost-sharing — prohibited by the No Surprises Act (ground ambulance is NOT
covered by the NSA; check state law for ground).

**Detection signals.**
- An out-of-network air-ambulance charge with a balance above in-network cost-sharing.
- "Out-of-network" cost-sharing applied to air-ambulance transport.

**Citation language.** Tier B: "Out-of-network air-ambulance services are subject to NSA
balance-billing protection; cost-sharing is calculated as in-network [No Surprises Act,
42 U.S.C. §300gg-112, src_TBD]."

**Severity.** High (very large dollar amounts typical).

**Common defenses.** Provider disputes NSA applicability. Response: confirm air (not
ground) transport; NSA covers air ambulance.

**Required evidence.** EOB, the air-ambulance bill, transport records.

**Recommended remediation (Tier C).** Assert NSA protection; provider/plan resolve via
IDR. Sequence via `negotiation_strategy`. For ground ambulance, route to state-law checks.
