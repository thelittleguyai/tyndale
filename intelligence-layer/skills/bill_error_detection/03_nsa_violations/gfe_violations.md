# Good Faith Estimate violations

**What this is.** For a self-pay / uninsured patient, the final bill materially exceeds the
Good Faith Estimate (GFE) the provider was required to give — the patient may dispute via
the NSA patient-provider dispute resolution (PPDR) process when the bill exceeds the GFE by
$400 or more.

**Detection signals.**
- A self-pay/uninsured bill that exceeds the GFE by at least $400.
- No GFE was provided at all before scheduled care.

**Citation language.** Tier B: "An uninsured/self-pay patient may dispute a bill that
exceeds the Good Faith Estimate by $400 or more through patient-provider dispute resolution
[No Surprises Act GFE/PPDR rules, 45 C.F.R. §149.610-.620, src_TBD]."

**Severity.** Medium–high (depends on the gap).

**Common defenses.** Provider cites unforeseen services. Response: unforeseen items still
require a process; the $400 threshold triggers PPDR rights.

**Required evidence.** The GFE, the final bill, and the scheduling timeline.

**Recommended remediation (Tier C).** Initiate PPDR within the deadline; sequence via
`negotiation_strategy`.
