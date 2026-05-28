# Network-status error (PAYER-SIDE)

**What this is.** The insurer processed in-network care as out-of-network (or vice versa),
applying the wrong cost-sharing tier. The EOB's network determination is the insurer's
claim; the detection signal is a GAP between it and the provider's actual network status on
the date of service.

**Detection signals.**
- EOB shows out-of-network for a provider that was in-network on the DOS.
- Out-of-network cost-sharing / balance billing applied to in-network care.
- A directory or coverage_connection_fhir check contradicts the EOB's network flag.

**Citation language.** Tier B: "The provider was in-network on the date of service; the
plan's in-network cost-sharing applies [plan SBC / provider directory, src_TBD]." (Pairs
with `02_coverage_application/in_out_network_errors.md`.)

**Severity.** High (large cost-sharing swings; possible balance-billing implications).

**Common defenses.** Insurer asserts out-of-network status. Response: provide directory
evidence of in-network status on the DOS.

**Required evidence.** EOB, proof of network status on the DOS, the SBC.

**Recommended remediation (Tier C).** Request reprocessing at the correct tier; escalate via
`negotiation_strategy`.
