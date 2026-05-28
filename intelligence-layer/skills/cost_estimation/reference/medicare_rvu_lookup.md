# Medicare RVU lookup (benchmark)

**Purpose.** Use the Medicare allowable rate as a sanity-check benchmark for the FAIR Health
UCR figure. Medicare rates are public and stable, so they anchor whether a UCR/charge is
reasonable.

**How to look up.**
- Inputs: CPT/HCPCS code + locality (Medicare locality / GPCI region).
- Compute: RVU components × conversion factor × locality adjustment → Medicare allowable.

**How to use it.**
- A commercial allowed amount is typically a multiple of Medicare (often ~1.2–3×, varies).
- If a charge is many multiples of Medicare, flag it as high and widen the band / note the
  variance.
- This is a **fallback/benchmark** when FAIR Health is unavailable (e.g., no license yet).

**Citation.** Tier A with source: "Medicare allowable for [code] in [locality] is ~$X
[Medicare RVU / Physician Fee Schedule, src_TBD]." Always name Medicare as the benchmark
source; never present it as the expected commercial price.
