# Collection fixtures

Small, representative seed data (~20 records per collection) for **local development
only**. They let the runtime query against something real before production data lands.

| File | Records (~) | Notes |
|---|---|---|
| `billing_codes.json` | 20 | CPT/HCPCS/ICD-10 — paraphrased descriptors (AMA owns verbatim CPT) |
| `error_detection_rules.json` | 18 | NCCI/MUE/modifier/preventive/upcoding/phantom narratives — paraphrased |
| `laws_regulations.json` | 18 | ERISA/ACA/NSA/MHPAEA/IRS §501(r)/EMTALA + state — representative text |
| `payer_policies.json` | 16 | CMS LCD/NCD + synthesized commercial policies — clearly fixture data |

Each file is a JSON object with a `_meta` block and a `records` array; every record
validates against the matching schema in `../schemas/`.

## Copyright

- **billing_codes** — generic descriptors close to but NOT verbatim from the CPT codebook.
- **error_detection_rules** — paraphrased policy text, not verbatim.
- **laws_regulations** — federal statutes/regulations are public domain; text here is
  representative (concise paraphrase), safe to replace with verbatim in Phase 5.
- **payer_policies** — clearly-synthesized examples, NOT real verbatim payer policies.

## Production

Replace these with real data before any production use. Production ingestion uses the
templates in [`docs/tyndale-spec/24_ingestion_templates.md`](../../../docs/tyndale-spec/24_ingestion_templates.md)
(Phase 5, Josh): real AMA CPT (license-gated), CMS NCCI/MUE, eCFR + state law, and payer
medical-necessity policies. Seed locally with `runtime/scripts/seed_fixtures.py`.
