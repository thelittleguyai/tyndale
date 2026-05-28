# Prior-authorization violations

**What this is.** A claim is denied or reduced for "no prior authorization" when auth was
not actually required, or when it was obtained, or when the requirement itself is
improper (e.g., for emergency care).

**Detection signals.**
- A "no prior auth" denial for a service the plan does not require auth for.
- Auth was obtained but not matched to the claim.
- Prior auth demanded for emergency services (not permitted).

**Citation language.** Tier B: "Prior authorization was not required for this service under
the plan / cannot be required for emergency services [plan policy; 42 U.S.C. §300gg-111(a)
for emergencies, src_TBD]."

**Severity.** Medium–high (full denials are large dollar).

**Common defenses.** Insurer asserts the requirement. Response: produce the auth or the
plan language showing none was required.

**Required evidence.** EOB/denial, the authorization record, the plan's prior-auth list.

**Recommended remediation (Tier C).** Appeal the denial; supply the auth or the
no-auth-required basis. Sequence via `negotiation_strategy`.
