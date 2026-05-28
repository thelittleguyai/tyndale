# Negotiation & Strategy — Diagnostic Index

Answer these questions to identify the applicable framework. Per P5, the output is a single
recommended path, not a menu. In V1-Lite, the Lead Planner uses this to recommend a SCRIPTED
ACTION the user takes themselves; the framework files build out in Full V1.

**Q1: Is this a self-funded employer plan?**
Signal: large/self-insured employer; plan documents reference ERISA; "ASO" administrator.
→ ERISA pathway. Load `frameworks/erisa_internal_appeal.md` (Full V1).

**Q2: Is this a fully-insured commercial plan?**
Signal: a state-regulated commercial plan (not self-funded).
→ ACA pathway (with ERISA overlay if employer-sponsored). Load `frameworks/aca_external_review.md` (Full V1).

**Q3: Is this a Medicare plan?**
Signal: Original Medicare or Medicare Advantage.
→ Medicare appeals. Load `frameworks/medicare_appeals.md` (Full V1).

**Q4: Is this a Medicaid plan?**
Signal: state Medicaid or a Medicaid managed-care plan.
→ State Medicaid appeals. Load `frameworks/medicaid_appeals.md` (Full V1).

**Q5: Did the user NOT choose this provider (ER, anesthesia, radiology, etc.)?**
Signal: emergency or out-of-network ancillary at an in-network facility (NSA territory).
→ NSA. Load `frameworks/nsa_open_negotiation.md`, then `frameworks/nsa_idr_process.md` (Full V1).

**Q6: Has the provider already been negotiated with directly?**
Signal: a prior direct negotiation attempt has stalled.
→ Escalate. Load `frameworks/direct_provider_negotiation.md` (escalation paths) (Full V1).

**Q7: Is the user uninsured/underinsured and the bill is from a nonprofit hospital?**
Signal: nonprofit hospital + financial hardship.
→ Charity care. Load `frameworks/charity_care_application.md` (Full V1).

**Q8: Is the bill in collections?**
Signal: a collections agency / credit-reporting threat.
→ Collections dispute. Load `frameworks/collections_dispute.md` (Full V1).

**Q9: Has the internal appeal already been exhausted?**
Signal: a final internal adverse determination has issued.
→ External review. Load `frameworks/aca_external_review.md` or `frameworks/state_external_review.md` (Full V1).

---

**V1-Lite output:** once the path is identified, recommend a specific scripted action (a phone
call script or a letter the user sends themselves), per P5, with the deadline surfaced (P2).
Letter generation is deferred to Full V1.
