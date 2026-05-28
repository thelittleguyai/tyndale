# Value with incomplete data (V1-Lite graceful-degradation playbook)

> mode: V1-Lite. Implements Part 3 of the Grounding & Graceful Degradation Doctrine. Mirrors the FHIR `partial_fhir_data.md` so behavior is identical across modes.

**Rule in every case: SHOW VALUE FIRST, then help the user climb to the next rung.** Never
make usefulness conditional on perfect inputs.

**The degradation ladder.**
- **Bill but no coverage terms / no EOB:** still run the code-level checks that need NO
  coverage data — bundling, upcoding, duplicates, MUE, modifier abuse, and phantom charges
  via encounter verification. Still benchmark the price against FAIR Health / Medicare. Still
  translate the bill to plain language. State what's deferred: *"I can't yet confirm whether
  your insurer applied your benefits correctly — that needs your EOB — but here's what I've
  already found."*
- **Coverage terms but no EOB:** compute what the user SHOULD owe given their benefits, so
  when the bill/EOB arrives they can spot a discrepancy themselves (and Tyndale can compare).
- **Just a confusing bill:** translate every line item to plain language, flag obvious red
  flags, and name the one or two documents that unlock the full audit — plus exactly how to
  get them (`helping_the_user_find_coverage_info.md`).

**Always pair "what I can't yet conclude" with "what I've already found" and "the one thing
that unlocks more."** That is the doctrine in practice.
