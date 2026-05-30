# send_email

mode: full-only — not implemented in V1-Lite

This tool is part of Full V1 and is GATED by the PreToolUse approval-token hook. See
`docs/tyndale-spec/22_tool_descriptions.md` for the full specification and
`docs/integration-contracts.md` §2.1 for the approval-gate contract. Build during Full V1
expansion when the gated email-send path lands. V1-Lite does not send emails on the user's behalf.

## When NOT to use

- Don't include any bill content, diagnosis, dollar amounts in medical context, case
  details, or any health information. The PreToolUse hook rejects emails containing PHI
  patterns (DL-47). Use a templated message via `template_id` from `ALLOWED_TEMPLATE_IDS`
  in `runtime/app/auth/email_templates.py` for any notification; if the template doesn't
  exist, add one to the allowlist after confirming it's PHI-free by construction (see
  `intelligence-layer/reference/no_phi_in_emails.md`).

## Arguments

- `template_id: str | None` — if set to an allowlisted value, skips the deep PHI scan
  (the template is vetted PHI-free by construction). Required for any notification email.
  An ad-hoc email with no `template_id` runs through `detect_phi()` over subject + body
  and is blocked on any match.
