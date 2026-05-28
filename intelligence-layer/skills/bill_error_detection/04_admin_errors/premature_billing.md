# Premature billing (billed before insurance processed)

**What this is.** The provider bills the patient the full charge before submitting the
claim to insurance or before the insurer has processed it — the patient is asked to pay
amounts the plan should adjudicate first.

**Detection signals.**
- A full-charge patient bill with no corresponding EOB.
- The claim was never submitted to the insurer.
- A patient balance that equals billed charges (no allowed-amount adjustment).

**Citation language.** Tier B where an in-network contract requires billing the plan first:
"In-network providers must submit to the plan and bill the patient only the plan-determined
cost-sharing [provider agreement / plan policy, src_TBD]."

**Severity.** Medium (often resolves once the claim is filed).

**Common defenses.** Provider claims insurance wasn't on file. Response: supply the
coverage info and request the claim be submitted.

**Required evidence.** The bill, the insurance card/coverage info, and any EOB status.

**Recommended remediation (Tier C).** Request the provider submit to insurance and reissue
after adjudication; sequence via `negotiation_strategy` if refused.
