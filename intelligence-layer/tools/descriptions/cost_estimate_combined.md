# cost_estimate_combined

mode: universal

## What it does
Returns a confidence-banded cost estimate for a procedure code at a location, combining
the Medicare baseline with hospital-MRF + TiC negotiated rates from `transparency_rates`.

## When to use
- The primary cost tool. Use whenever Math Person needs a fair-price reference or a
  patient-facing cost range. Prefer it over the per-source tools.

## When NOT to use
- When you need a single source in isolation (use `cost_estimate_medicare_rvu`,
  `cost_estimate_hospital_mrf`, or `cost_estimate_tic`).

## Arguments
- `code` (string, required) — CPT/HCPCS code.
- `location_zip3` (string, optional) — 3-digit ZIP (HIPAA Safe Harbor).
- `payer` (string, optional); `hospital_id` (string, optional).

## Returns
```json
{"code":"70553","location_zip3":"021","central_estimate":620.0,"low_estimate":540.0,
 "high_estimate":700.0,"sources_used":["medicare_pfs","tic_mrf"],
 "confidence_summary":"...","methodology":"..."}
```
ALWAYS a low/central/high band — NEVER a point number (No Surprises Act good-faith
framing). Falls back to the Medicare baseline (±35% band) when no negotiated rates exist.

## Notes
DL-54: returns code NUMBERS + dollars only; the UI maps the code to a placeholder
descriptor. `source='trilliant'` is skipped until that adapter lands (DL-50).
