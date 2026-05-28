# SMART-on-FHIR OAuth

> mode: full-only — not active in V1-Lite. See `manual_upload_flow.md` for the V1-Lite coverage path.

**What this covers.** The SMART-on-FHIR app-launch / authorization sequence Tyndale uses with
1upHealth to obtain access to a user's FHIR resources.

**Flow (Skill describes; engineers implement).**
1. App launch / authorization request (standalone launch) with the required scopes
   (patient/Coverage.read, patient/ExplanationOfBenefit.read, patient/Claim.read).
2. User authenticates with their payer through 1upHealth and consents.
3. Authorization code → token exchange → access token + refresh token.
4. Store tokens securely (engineering: secrets in runtime env / secure storage).
5. Refresh flow on expiry; re-prompt only if the refresh token is invalid.

**What this Skill owns vs. engineering.** The Skill describes the sequence and what to do
with the returned data; the actual OAuth client, token storage, and refresh are built by the
engineers (runtime).

**Failure handling.** Expired/invalid tokens, payer-side rate limits, and consent revocation
→ see `connection_troubleshooting.md`.
