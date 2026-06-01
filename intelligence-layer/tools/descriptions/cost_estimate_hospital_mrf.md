# cost_estimate_hospital_mrf

mode: universal

## What it does
Returns the negotiated / cash / gross charges a SPECIFIC hospital published for a code,
from its CMS-mandated machine-readable file (`transparency_rates` source=`hospital_mrf`).

## When to use
- The user's care is (or would be) at a known hospital and you want that hospital's own
  posted prices for a code.

## When NOT to use
- For a blended market estimate (use `cost_estimate_combined`); for payer-specific rates
  across providers (use `cost_estimate_tic`).

## Arguments
- `code` (string, required) — CPT/HCPCS/DRG.
- `hospital_id` (string, required) — CMS provider number (CCN).

## Returns
```json
{"code":"70553","hospital_id":"330101",
 "rates":[{"payer":"Aetna","rate":620.0,"rate_type":"negotiated","confidence":0.85}]}
```

## Notes
New hospitals land in `transparency_rates_staging` first (DL-59) until a ≥90%
extraction-confidence sample passes. DL-54: numbers only, no CPT descriptors.
