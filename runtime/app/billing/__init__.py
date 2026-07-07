"""Billing (Item 4, DL-16) — Stripe subscription + one-free-analysis cap.

DARK SCAFFOLD: every path here is inert while settings.enable_billing is False (the routes 404,
the audit-gate dependency is a no-op, the settings UI hides). Stripe is walled off from PHI
(DL-49): we send only the user UUID as client_reference_id and let Stripe's hosted Checkout
collect email/payment — never an email, bill detail, or health information from us.
"""
