# In-network / out-of-network errors

**What this is.** In-network care is billed or allowed as out-of-network (higher
cost-sharing, balance billing), or the allowed amount exceeds the in-network contracted
rate. Also covers check 23 (allowed amount vs. contracted rate).

**Detection signals.**
- An in-network provider's claim processed at out-of-network cost-sharing.
- Allowed amount above the plan's in-network contracted rate.
- Balance billing where an in-network contract prohibits it.

**Citation language.** Tier B: "The provider was in-network on the date of service; the
plan's in-network cost-sharing applies and balance billing is contractually prohibited
[plan SBC / provider agreement, src_TBD]." (Often a payer-side finding —
cross-ref `05_payer_side_errors/network_status_error.md`.)

**Severity.** High (large dollar swings; possible balance-billing prohibition).

**Common defenses.** Insurer claims the provider was out-of-network. Response: verify the
provider's network status on the DOS (directory / coverage_connection_fhir).

**Required evidence.** EOB, proof of the provider's network status on the DOS, the SBC.

**Recommended remediation (Tier C).** Request reprocessing in-network; escalate via
`negotiation_strategy`.
