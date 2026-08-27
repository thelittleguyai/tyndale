# Go-live checklist (pre-launch confirmations)

Companion to `SECURITY_GO_LIVE.md` (the security/config gates). This file holds the
**content and substantiation** confirmations that must be true before a public launch.
Nothing here creates or touches staging/production infrastructure.

## Substantiation — public figures on the landing page

- [ ] **$504,100 "recovered for members" (B4)** — *stays on the page per Brock 2026-08-18
      (B2).* Owed before launch: a **substantiation entry + as-of date (Brock)** in the
      analytics substantiation file, naming what the figure counts, the period, and what
      updates it. A public dollar figure next to a "we're early" beta band needs a paper trail.
- [ ] **C1 / C2 citations (Brock)** — the two landing claims still held for a source (the
      "$400 dispute right" tip among them) ship only with their citations.
- [ ] **B11** — the page never claims "80% of medical bills contain errors" (banned,
      unsupported). CI grep stays clean.

## Copy gates

- [ ] Orchestration script at the signed-off version (v1.1 as of 2026-08-18); zero
      `[PLACEHOLDER-eng]` values (`tests/test_orchestration_script.py` pins it; the staging
      boot refuses otherwise).
- [ ] Inbound copy from Brock landed or explicitly held: A4 four-branch wrong-document
      strings, D5 clean-bill/negotiation copy, A6 error taxonomy + §3.10, §3.8 nudge-split
      confirmation.

## Data activation

- [x] Priors tranche 1 received (`intelligence-layer/reference/priors/`) — *2026-08-27:
      5/7 entries LIVE (deductible_amount, oop_max_amount, coinsurance_percent, copay_pcp,
      copay_specialist); copay_er + household_income remain dark BY DESIGN (no defensible
      prior yet — the tranche says so explicitly and the loader keeps them point-form).*
- [ ] 50-state NSA seed + rules/laws corpora content (Brock's program) — balance-billing
      check + retrieval quality.
