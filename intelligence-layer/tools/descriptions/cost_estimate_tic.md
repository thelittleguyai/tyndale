# cost_estimate_tic

mode: universal

## What it does
Returns a SPECIFIC commercial payer's negotiated rates for a code, from its
Transparency-in-Coverage machine-readable file (`transparency_rates` source=`tic_mrf`),
after DL-63 ghost-rate filtering.

## When to use
- You know the user's payer and want that payer's negotiated rate for a code.

## When NOT to use
- For a blended estimate (use `cost_estimate_combined`); for a hospital's posted prices
  (use `cost_estimate_hospital_mrf`).

## Arguments
- `code` (string, required); `payer` (string, required) — normalized payer name.

## Returns
```json
{"code":"70553","payer":"UnitedHealthcare",
 "rates":[{"rate":540.0,"rate_type":"negotiated","confidence":0.78}]}
```

## Notes
Ghost rates (rate=0, out of 30–500% of Medicare, single-occurrence) are filtered at
ingest (DL-63, tunable). `confidence` reflects corroboration + distance from baseline +
recency. DL-54: numbers only.
