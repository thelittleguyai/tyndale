# Connection troubleshooting

> mode: full-only — FHIR connection errors. (Manual mode has no live connection; its issues are extraction-confidence and missing-document problems — see the manual-mode files.)

**What this covers.** Common FHIR/1upHealth connection error patterns and how to surface them
to the user clearly (and what Tyndale can still do meanwhile).

**Common patterns.**
- **Expired / invalid token:** trigger the refresh flow; if the refresh token is invalid,
  prompt a re-connect with a one-tap path (per P1 — make it trivial).
- **Payer-side rate limits / outages:** back off and retry; tell the user the payer is
  temporarily unavailable and Tyndale will re-check automatically.
- **Consent revoked / scope missing:** explain plainly what access is needed and why, and how
  to re-grant.
- **Payer not supported by 1upHealth:** fall back to **manual-upload mode** so the user is
  never blocked (see `manual_upload_flow.md`).

**Voice.** Surface errors in plain language, not technical jargon. Always pair an error with
what Tyndale CAN still do right now (graceful degradation), so a connection problem never
dead-ends the user.
