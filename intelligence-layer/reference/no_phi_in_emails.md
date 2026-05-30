# No PHI in Emails (DL-47)

Tyndale's firm architectural rule: email content is PHI-free by construction.
Magic-link sign-in, account notifications, "your report is ready" — fine. Bill
content, diagnosis, dollar amounts in medical context, case details, any health
information — never.

## How it's enforced

Runtime invariant via the PreToolUse hook on `send_email` (Phase CO-8). Two paths:

1. **Template-allowlisted (preferred).** Set `template_id` to an allowlisted value
   in `runtime/app/auth/email_templates.py` `ALLOWED_TEMPLATE_IDS`. The template's
   content is vetted as PHI-free by construction. The deep PHI scan is skipped for
   performance.

2. **Ad-hoc with deep scan.** If `template_id` is missing or non-allowlisted, the
   hook runs a deep PHI scan (`detect_phi`) over subject + body. False positives are
   acceptable; false negatives are unacceptable. Any PHI pattern hit → the send is
   blocked + a `phi_block` `audit_events` row is written. The block surfaces as
   `approved=False` (a normal, audited outcome), never as a 500.

What the scan catches: dollar amounts within ~80 chars of a billing keyword;
medical codes (CPT/HCPCS/ICD-10/NDC); identifiers (SSN, payer member-ID shapes,
MRN/account/claim numbers); PHI-suggesting phrases ("your bill", "you owe",
"explanation of benefits", …); and common diagnosis terms.

## Adding a new template

1. Draft the template content in `runtime/app/email/templates/<template_id>.html`
   (and a `.txt` fallback).
2. Verify the template's variable substitutions can NEVER produce PHI given the
   surrounding code paths. Templates must use generic phrases ("there's an update
   on one of your cases") not specific ones ("your bill of $1,200 is ready").
3. Add the `template_id` to `ALLOWED_TEMPLATE_IDS` with a comment explaining the
   variable-substitution review.
4. Cover it with a test in `runtime/tests/test_send_email_phi_guardrail.py`
   confirming the template-allowlisted path passes.

## Why this rule exists

Email is sent via SendGrid, which is excluded from the BAA list (DL-49) on the
basis that no PHI flows through it. If PHI ever reaches email, the SendGrid
exclusion is invalid and a BAA becomes required. This rule keeps the BAA chain at
5 (Anthropic, Azure, AWS, Voyage AI, 1upHealth) rather than 6.

See DL-47 for the locked decision; DL-49 for the BAA-chain consequence.
