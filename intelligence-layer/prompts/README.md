# Prompts — engineering notes

Authoring here is Brock's. This file carries the engineering constraints a prompt editor
must know before changing anything.

## The canary codes: 02417 · 05821 · Z4411 (re-picked 2026-09-18)

The worked-example codes that appear in prompts, skills, and tool descriptions
(e.g. `skills/bill_error_detection/06_encounter_verification/lineitem_plain_language.md`'s
"MRI brain w/ + w/o contrast (02417)") are **deliberately the same codes as the e2e
harness's `FIXTURE_MARKERS`** (`runtime/scripts/e2e_scenarios/run_scenarios.py`).

**Why these three (Brock 2026-09-17):** the original set — 70553 (MRI family), A9579 (a real
contrast agent), 36000 (venipuncture, and a substring of innocent amounts) — were real codes,
so legitimate reasoning could name them (a 70551 bill's family check named 70553 on
2026-08-25). The replacements are *valid in FORMAT and structurally never assigned*: `02417`
and `05821` sit in the empty five-digit CPT gap between anesthesia (ends 01999) and surgery
(starts 10004); `Z4411` uses the HCPCS Level II letter Z, which is not nationally assigned.
A canary that can never arise in real reasoning only sings for fabrication. (Verified against
the billing_codes corpus + the CPT/HCPCS range shapes before adoption.)

That coupling is a tripwire, and it has already fired for real: on 2026-08-17 the first
full dev sweep caught the translate agent echoing the (then-)70553 example into a user's
persisted line items when a photographed bill's OCR came back thin. Any marker code
appearing in a pipeline OUTPUT means non-document content leaked into user data — the
runtime's translate-grounding guard now drops such items, and the harness fails the run.

**If you swap an example code, tell engineering so the marker set moves in lockstep.**
A prompt example that stops matching the markers is a canary that no longer sings; new
example codes should be ADDED to `FIXTURE_MARKERS`, never silently divergent. No scenario
may ever use a marker code as legitimate document data (the harness README note on
`captured_bill_photo` records the day one did).
