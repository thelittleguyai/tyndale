# Tyndale Legal Documents — Notes for Developer & Claude Cowork

This folder (`legal_final/`) contains four launch-candidate legal documents for
Tyndale, written to be placed into the platform:

1. `01_terms_of_service.md` — Terms of Service (disclaimers folded in)
2. `02_privacy_policy.md` — Privacy Policy (includes the cookie/tracking section)
3. `03_improvement_consent.md` — the separate, optional data-improvement opt-in
4. `04_state_specific_rights_addendum.md` — nationwide state-rights rider

## Status

These are **launch-candidates**: written as final, platform-ready text. Before they
go live, two things are required:

1. **Complete the short "Before publishing" checklist at the top of each document**
   (business address and contact emails — the only must-be-yours fields left open).
2. **Attorney confirmation.** An attorney has not reviewed these. They were written
   to the most likely-correct legal posture (see below), but a healthcare-and-
   privacy attorney must confirm before publication. This is especially true for
   the arbitration / class-waiver / liability sections in the Terms, which are
   enforceability-sensitive and state-specific.

## Key assumptions baked into these documents

- **Entity:** The Little Guy LLC d/b/a Tyndale.
- **Geography:** Nationwide (US only). No international/GDPR coverage.
- **Governing law:** Utah (default for the LLC; confirm with counsel).
- **Subscription:** $11.99/month or $100/year, unlimited use, cancel anytime
  effective at the end of the current billing period, no prorated refunds.
- **HIPAA posture:** Written to the **non-HIPAA-covered, consumer-health-app**
  posture, governed by the FTC Act / FTC Health Breach Notification Rule and state
  privacy and health-data laws. This is the most likely-correct posture for
  V1-Lite, where the user voluntarily uploads their own documents for their own
  benefit (not data handled on behalf of a covered entity). No formal Notice of
  Privacy Practices is included, consistent with not claiming covered-entity status.

## THREE ITEMS TO REVISIT (route to Claude Cowork)

**REVISIT ITEM 0 — Contact emails (support + privacy).** Not yet established. Every
document has these marked as fill-ins. Before publishing, create the two addresses
(e.g., a support@ and a privacy@ on the Tyndale domain — they can be the same inbox
to start, but a distinct privacy@ is good practice for a health product) and insert
them everywhere the documents say `[support email]` and `[privacy contact email]`.
The business mailing address (336 E University Pkwy #1043, Orem, Utah 84058) and
governing-law state (Utah) are already filled in.

**REVISIT ITEM 1 — Analytics & tracking.** The Privacy Policy and its cookie section
are currently written to the safe default: privacy-respecting, first-party analytics
only, and **NO advertising/retargeting trackers** (no Meta Pixel, Google Ads pixel,
TikTok pixel, etc.) anywhere — and especially not on any page that handles bills or
health data. This is deliberate: advertising trackers on health-data pages have
driven major FTC actions and lawsuits against health-adjacent apps.

Action for the developer + Cowork: confirm exactly which analytics tool (if any)
will run at launch. Acceptable: none, or a privacy-respecting first-party tool
(e.g., Plausible, Fathom). NOT acceptable for this product: any advertising/
retargeting pixel on pages handling health or billing data. Once the tool is
confirmed, update the named tool in the Privacy Policy's "Cookies & tracking"
section so the policy accurately describes what actually runs. **The policy must
match reality — a policy that says "no ad tracking" while a pixel is present is a
misrepresentation and an enforcement risk.**

**REVISIT ITEM 2 — 1upHealth / Full V1 HIPAA re-look.** These documents are written
for V1-Lite (manual user upload), where the non-HIPAA consumer-app posture almost
certainly applies. When Full V1 adds the 1upHealth integration (pulling the user's
coverage/clinical data via patient-authorized API), the legal analysis should be
re-examined by counsel. Patient-directed API access usually KEEPS an app outside
HIPAA, but the integration's structure and contracts are the most likely place the
analysis could shift toward business-associate status. Do not launch Full V1's
1upHealth connection without this re-look.

## What is intentionally NOT in this folder

- Notice of Privacy Practices — omitted on purpose (consistent with non-covered-
  entity posture). Add only if counsel determines covered-entity status.
- Standalone Acceptable Use Policy — its core prohibitions are folded into the
  Terms. A separate AUP can be added later if desired.
- Internal/contractor agreements (IP assignment, contractor terms, BAAs) — separate
  internal pack, not part of the user-facing documents. Earlier draft versions of
  the user-facing pack (with full attorney-markup notes) are in the sibling
  `legal/` folder for the attorney's reference.
