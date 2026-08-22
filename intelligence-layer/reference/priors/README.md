# Priors — receiving dock for Brock's `missing_data_spectrum` tranches

Brock delivers the researched priors table **in tranches**. Each tranche is one JSON file
in this directory, updating SOME entries; the runtime merges tranches **per entry** over
the engineering placeholders at load time. An entry activates user-visible dollar RANGES
the moment its tranche sets `"placeholder": false` — no code change, no whole-table
replacement, and untouched siblings stay dark (point-form only) until their own tranche.

## File shape (`*.json`, merged in filename order — later files win per entry)

```json
{
  "source": "missing_data_spectrum_2026-08-xx.md",
  "as_of": "2026-08-20",
  "entries": {
    "deductible_amount": {
      "low": 500, "base": 1700, "high": 6000, "unit": "usd",
      "placeholder": false,
      "note": "KFF 2025 EHBS individual deductible distribution (p25/median/p90)"
    }
  }
}
```

- `entries` keys are the runtime's input names (`deductible_amount`, `oop_max_amount`,
  `coinsurance_percent`, `copay_specialist`, `copay_er`, `household_income`). A key the
  runtime doesn't know is logged and ignored, never a crash.
- Each entry carries its own provenance: the file-level `source`/`as_of` apply unless the
  entry overrides them. `placeholder` defaults to **true** (dark) unless stated.
- Partial entries are fine: omitted fields keep the current value.
