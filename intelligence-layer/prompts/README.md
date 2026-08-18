# Prompts — engineering notes

Authoring here is Brock's. This file carries the engineering constraints a prompt editor
must know before changing anything.

## The canary codes: 70553 · A9579 · 36000

The worked-example codes that appear in prompts, skills, and tool descriptions
(e.g. `skills/bill_error_detection/06_encounter_verification/lineitem_plain_language.md`'s
"MRI brain w/ + w/o contrast (70553)") are **deliberately the same codes as the e2e
harness's `FIXTURE_MARKERS`** (`runtime/scripts/e2e_scenarios/run_scenarios.py`).

That coupling is a tripwire, and it has already fired for real: on 2026-08-17 the first
full dev sweep caught the translate agent echoing the 70553 example into a user's
persisted line items when a photographed bill's OCR came back thin. Any marker code
appearing in a pipeline OUTPUT means non-document content leaked into user data — the
runtime's translate-grounding guard now drops such items, and the harness fails the run.

**If you swap an example code, tell engineering so the marker set moves in lockstep.**
A prompt example that stops matching the markers is a canary that no longer sings; new
example codes should be ADDED to `FIXTURE_MARKERS`, never silently divergent. No scenario
may ever use a marker code as legitimate document data (the harness README note on
`captured_bill_photo` records the day one did).
