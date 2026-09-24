# Tyndale — Real, Canonical Example Documents for the "Here's What This Looks Like" Feature

Research memo. Compiled September 2026. Every source below was either (a) fetched directly and quoted/paraphrased from the live page or PDF, or (b) surfaced by search and flagged **⚠️ UNVERIFIED** where I could not independently open and confirm the content (login walls, JS-rendered pages, or a fetch timeout). Do not ship an ⚠️ item as "verified real" in-app copy without a human re-check — the URL pattern is real and plausible, but I did not personally see the rendered content.

---

## 1. Schedule of Benefits vs. Summary of Benefits and Coverage (SBC)

### 1.0 They are NOT the same document — resolve this first

- **SBC (Summary of Benefits and Coverage)** = a federally mandated, **uniform, 4–8 page** template (ACA §2715 / 29 CFR 2590.715-2715). Every plan and issuer must produce one using the *exact same layout and terms*, precisely so consumers can compare plans side by side. Confirmed directly: the current CMS sample-completed SBC PDF is **5 pages** (I fetched it — see 1.1 below), consistent with the "4–8 page" range.
- **Schedule of Benefits / Summary of Benefits** *inside* a Summary Plan Description (SPD), Evidence of Coverage (EOC), or Certificate of Coverage = the **long, plan-specific, legally binding contract document** — the detailed benefit schedule with full exclusions, definitions, CPT/service-level cost-sharing rules, and appeal rights. This is *not* standardized in format across insurers.
- Kaiser Permanente's own consumer education page makes this distinction explicitly and in plain language:
  > "**Evidence of Coverage (EOC)** — Your fully detailed plan document... The Evidence of Coverage is like a contract between you and your health plan... Some plan types use a name other than *Evidence of Coverage* for this document. Other names might include *Certificate of Insurance, Summary Plan Description, Certificate of Coverage,* or *Member Handbook*." vs. "**Summary of Benefits and Coverage (SBC)** — Your summarized plan document... in plain language, and in a standard format that's used throughout the health care industry."
  Source (fetched, verified): https://healthy.kaiserpermanente.org/learn/understand-health-plan-documents

**Which one does a bill audit need?** Both, for different jobs. The **SBC** is the fast sanity-check: it gives the overall deductible, out-of-pocket max, network vs. out-of-network split, and copay/coinsurance for broad categories ("Specialist visit," "Imaging (CT/PET scans, MRIs)," "Emergency room care"). It is *not* granular enough to audit a specific CPT code. The **Schedule of Benefits inside the SPD/EOC/Certificate of Coverage** is what you need for the actual line-item audit — it defines exactly how a given service class is adjudicated, prior-authorization rules, and any service-specific deductibles/limits (the sample SBC below shows a plan with *both* a $500/$1,000 overall deductible *and* a separate $300 drug deductible — a detail an auditor must track back to the SPD/EOC, not just the SBC).

**Where each typically lives:**
- SBC: insurer member-portal "plan documents" page; employer HR/benefits site (during open enrollment); for ACA marketplace plans, on the plan's own page at healthcare.gov (click the plan name → "Plan Documents"). UHC also publishes a consumer explainer page confirming issuers must supply this on request: https://www.uhc.com/understanding-health-insurance/how-does-health-insurance-work/summary-of-benefits-and-coverage ⚠️ UNVERIFIED (found via search of uhc.com, not opened directly — but the URL is a real UHC page in the same family as the EOB and ID-card pages I did verify on uhc.com).
- Schedule of Benefits / SPD / EOC: same insurer portal, usually a different link labeled "Evidence of Coverage," "Certificate of Coverage," "Benefit Booklet," or "Plan Document" (not "SBC"); or the employer's benefits administration site (Workday/ADP/etc.) under "plan documents."

### 1.1 Official SBC blank template (CMS/DOL)

1. **CMS — SBC Template (blank, accessible format, Nov 2019).** PDF: https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/sbc-template-accessible-format-11-2019.pdf
2. **DOL — SBC Template page**, which hosts the same template for employer plan sponsors, with instructions on distribution rules (must be given at shopping, enrollment, each new plan year, and within 7 business days of a request). Fetched and verified: https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/affordable-care-act/for-employers-and-advisers/sbc-template-2 → links to PDF https://www.dol.gov/sites/dolgov/files/EBSA/laws-and-regulations/laws/affordable-care-act/for-employers-and-advisers/sbc-template-2.pdf
3. **CMS — "Summary of Benefits & Coverage & Uniform Glossary" hub page** (the authoritative index CMS/HHS/DOL maintain jointly). Fetched and verified: https://www.cms.gov/marketplace/health-plans-issuers/summary-benefits-coverage

### 1.2 Official CMS "Sample Completed SBC" (this is the one to screenshot)

**Fetched and verified directly** — full text extracted from the live PDF, January 2025 accessible-format version, still the current file CMS links from its SBC hub page:
https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/english-sample-completed-sbc-accessible-format-012825.pdf

Exact layout confirmed from the PDF (5 pages total, "Insurance Company 1: Plan Option 1," Coverage Period 01/01/2025–12/31/2025, PPO, Family):

- **Page 1 — "Important Questions" table.** Two columns: *Important Questions* | *Answers* | *Why This Matters*. Real rows in the sample: "What is the overall deductible?" → **$500/individual or $1,000/family**; "Are there other deductibles for specific services?" → **Yes, $300 for prescription drug coverage and $300 for occupational therapy** (this is the exact kind of hidden sub-deductible an audit tool must catch); "What is the out-of-pocket limit for this plan?" → **network: $2,500 individual/$5,000 family; out-of-network: $4,000/$8,000**; "What is not included in the out-of-pocket limit?" → copayments for certain services, premiums, balance-billing charges; "Will you pay less if you use a network provider?"; "Do you need a referral to see a specialist?"
- **Pages 2–3 — "Common Medical Event" grid.** Left column groups services under a real-world trigger ("If you visit a health care provider's office or clinic," "If you have a hospital stay," "If you are pregnant," "If you need immediate medical attention"). For each, a row of *Services You May Need* (e.g., "Primary care visit," "Specialist visit," "Diagnostic test (x-ray, blood work)," "Imaging (CT/PET scans, MRIs)," "Generic drugs (Tier 1)," "Emergency room care") with **two "What You Will Pay" columns side by side: Network Provider (You will pay the least) vs. Out-of-Network Provider (You will pay the most)** — e.g., "Specialist visit: $50 copay/visit (network) vs. 40% coinsurance (out-of-network), preauthorization required." A footnote states: *"All copayment and coinsurance costs shown in this chart are after your deductible has been met, if a deductible applies."*
- **Page 4 — Excluded Services list** ("Cosmetic surgery," "Dental care (Adult)," "Routine eye care (Adult)") and Other Covered Services list, plus continuation-of-coverage and grievance/appeal rights, and the required multi-language access taglines (Spanish, Tagalog, Chinese, Navajo, Pennsylvania Dutch, Samoan, Carolinian, Chamorro).
- **Page 5 — "Coverage Examples."** Three standardized scenarios required by CMS regulation — "Peg is Having a Baby," "Managing Joe's Type 2 Diabetes," "Mia's Simple Fracture" — each showing Total Example Cost, then a cost-sharing breakdown (Deductibles/Copayments/Coinsurance/Limits or exclusions) and a bottom-line "The total [Peg/Joe/Mia] would pay is $X."

### 1.3 One more real-world grounding source

- HealthCare.gov glossary entry, confirming the plain-English definition and when consumers receive an SBC (shopping, enrolling, each new plan year, or within 7 business days of a request). Fetched and verified: https://www.healthcare.gov/glossary/summary-of-benefits-and-coverage/

---

## 2. Explanation of Benefits (EOB) — major payers + Medicare's equivalent

Universal framing for the app: **an EOB is not a bill.** Every source below says this in nearly identical language. The fields that recur across every payer, in the order they usually appear: patient/subscriber name & member ID, provider name, date of service, claim number, **billed/provider charges**, **allowed amount**, **plan paid / paid by insurer**, deductible applied, copay, coinsurance, **patient responsibility / "what you owe"**, and a **remark/reason code** key at the bottom.

### 2.1 Best single starting reference: CMS's own generic EOB guide + sample

CMS built a plain-language, payer-agnostic "how to read an EOB" page specifically for its Medical Bill Rights initiative, with a downloadable annotated sample PDF. This is the strongest anchor for the app's default EOB annotation because it is neutral (not branded to one insurer) and literally numbers its own callouts.

- Page (fetched, verified): https://www.cms.gov/initiatives/your-patient-rights/medical-bill-rights/get-help/medical-bill-guides-resources/how-read-health-insurance-explanation-benefits (canonical target of cms.gov/medical-bill-rights/help/guides/explanation-of-benefits)
- Sample PDF, "Reading Your Explanation of Benefits (EOB)," Pub. #11819, Rev. May 2022 (fetched, verified — full text extracted): https://www.cms.gov/files/document/11819-sample-explanation-benefits-508.pdf

The CMS sample PDF already ships with **8 numbered callouts** on a mock EOB table (columns: Line No. / Service Description / Date of Service / Claim Status / Provider Charges / Allowed Charges / Co-Pay / Deductible / Coinsurance / Paid by Insurer / Remark Code / What You Owe):
1. Phone Numbers — "You can call your health plan if you have questions..."
2. Payee — "the person who will receive any reimbursement for over-paying the claim"
3. Service Description — "the health services you received, like a medical visit, lab test, or screening"
4. Provider Charges — "the amount your provider bills for your visit"
5. Allowed Charges — "the amount your provider will be paid; this may not be the same as the Provider Charges"
6. Paid by Insurer — "the amount your health plan will pay to your provider"
7. What You Owe — "the amount you owe after your insurer has paid everything else... Payments made directly to your provider may not be subtracted from this amount"
8. Remark Code — "a note from the health plan that explains more about the costs, charges, and paid amounts for your visit"

### 2.2 UnitedHealthcare

- Page (fetched, verified): https://www.uhc.com/understanding-health-insurance/how-does-health-insurance-work/explanation-of-benefits
- Direct link to UHC's own sample EOB flyer PDF (linked from the page above, same uhc.com domain): https://www.uhc.com/content/dam/uhcdotcom/en/general/understanding-your-eob-flier.pdf
- Confirmed field list from the page text: name, plan info + member ID, provider, claim number and status, service description + date, **total cost of services**, **how much was paid by your health insurance plan**, costs your plan didn't cover, any amount paid from an HRA, **what you owe**, and (on some EOBs) **out-of-pocket expenses that count toward your deductible**.
- Medicare Advantage/Part D-specific UHC EOB page also exists: https://www.uhc.com/medicare/resources/ma-pdp-information-forms/explanation-benefits.html

### 2.3 Aetna

- Official member-facing "Understanding your Explanation of Benefits (EOB) statement" guide, fetched and verified in full from Aetna's own secure-content domain: https://member.aetna.com/memberSecure/assets/pdfs/EOB%20Guide.pdf
  Confirmed sections, in order: (1) name/address/member ID/group number/group name/customer service info; (2) "It's easy to track your spending and savings" — what you owe, how much you saved in-network, **and the remaining amount to meet your yearly in-network family or individual deductible**; (3) "Your payment summary"; (4) "Your claims up close" — per-claim breakdown of benefit application, plan paid, amount owed; (5) "Your benefit balances" — summary of financial limits for the benefit year; (6) "Messages." Explicit disclaimer: *"For illustrative purposes only. This is a sample EOB and does not reflect actual charges..."* — i.e., Aetna itself labels this a mock-up, which is exactly the kind of annotated sample Tyndale needs.

### 2.4 Anthem / Elevance Health

- Anthem's own claims-process page (fetched, verified): https://www.anthem.com/member-resources/claims — confirms the EOB is generated automatically after claim adjudication ("you'll receive an Explanation of Benefits (EOB) showing what we paid, and what you owe"), viewable by logging in or via the Sydney Health app; also confirms Anthem does **not** send an EOB when a service is fully covered by a flat copay with nothing further owed.
- Anthem does not appear to publish a public, unauthenticated sample-EOB image on anthem.com itself (its EOB samples live behind login). Third-party benefits-administration help sites host what they present as Anthem's own EOB layout description (four components: Claim Tracking Details, Service Details, Charges, and remaining balances) — ⚠️ UNVERIFIED by direct fetch (page did not render): https://onpartners.zendesk.com/hc/en-us/articles/11393946275348-Understanding-your-Anthem-Explanation-of-Benefits-EOB — treat as directional only until confirmed against a real Anthem member's EOB or an official Anthem PDF.

### 2.5 Cigna

- Official page, fetched and verified in full: https://www.cigna.com/knowledge-center/explanation-of-benefits — gives an explicit **page-by-page structure**: *Page 1: Summary* (name/details, services received, who provided them, amount billed, discounts from in-network care, amount paid by plan, amount not covered, any HRA/HSA/FSA amount applied, additional costs owed); *Page 2: Glossary and Appeal Information*; *Page 3: Detailed Breakdown* (specific cost detail, **how much counts toward your annual deductible**, language assistance, state-specific appeal info).
- Real Cigna-hosted sample/guide PDFs on Cigna's own domain (found via search, both are literal cigna.com static asset URLs consistent with the domain I did verify): https://www.cigna.com/static/www-cigna-com/docs/846894-eob-v1.pdf and https://www.cigna.com/static/www-cigna-com/docs/832700_e_Choice_Fund_EOB_v2.pdf ⚠️ UNVERIFIED by direct fetch (not opened this session, but on Cigna's verified domain).

### 2.6 Blue Cross Blue Shield (multiple plans — BCBS is not one company, so cite the specific licensee)

- **Blue Cross NC**, fetched and verified in full: https://www.bcbsnc.com/members/knowledge-center/how-to-read-eob — confirms **Provider charges/billed amount**, **amount we paid / covered amount**, **allowed amount** ("the maximum amount your insurance will pay for a service... found in Claim Details in the Allowed Amount column"), reason codes, and remaining balance; explicitly instructs members to compare the EOB against the provider bill line by line.
- **Blue Shield of California** has its own equivalent page (found via search, real bcbs domain, not opened this session): https://www.blueshieldca.com/en/home/help-and-support/how-to-read-eob ⚠️ UNVERIFIED.
- **Blue Cross MN** equivalent (found via search): https://www.bluecrossmn.com/understanding-health-insurance/understanding-healthcare-costs/how-read-eob ⚠️ UNVERIFIED.
- **BCBS of Illinois / Texas** run an "explanation of your EOB" post on their shared Connect blog platform (found via search, real bcbstx/bcbsil domain): https://connect.bcbstx.com/understanding-benefits/b/weblog/posts/an-explanation-of-your-explanation-of-benefits-eob and the Illinois mirror at https://connect.bcbsil.com/my-coverage-explained/b/weblog/posts/an-explanation-of-your-explanation-of-benefits-eob ⚠️ UNVERIFIED (not opened this session).

### 2.7 Kaiser Permanente

- Fetched and verified: https://healthy.kaiserpermanente.org/learn/understand-health-plan-documents — Kaiser's own three-way definition names EOB as "A statement of care you've received... after you see a care provider for a health service, you will likely get an EOB. This statement summarizes the care you've gotten in a given time frame (like your monthly credit card statement)." Confirms EOBs are found by signing in to kp.org → "Benefits" → "View benefit summary" or "Coverage documents."

### 2.8 Humana (SmartEOB®)

This is the strongest payer-branded example in the whole set — I pulled the **actual live sample PDF and the accompanying reader's guide PDF**, both hosted on Humana's own assets domain and linked from Humana's own public plain-language policy page.

- Landing/context page, fetched and verified: https://www.humana.com/member/dental-plain-language-policy (the SmartEOB section applies to medical/dental alike; Humana explicitly labels it "Explanation of Benefits (SmartEOB)")
- **Sample SmartEOB PDF**, fetched and verified in full (9 pages, mock "Firstname A Lastname" data): https://assets.humana.com/is/content/humana/SmartEOB_Standardpdf — shows Total billed charges → Plan discounts/exclusions → Benefit exclusions → Allowed amount → Amount plan pays → **Total amount you may owe provider**, split separately for medical/prescription vs. dental, plus a **claim-level table** (Claim #, Processed date, Patient account #, provider, reason code) and a big **"THIS IS NOT A BILL"** banner.
- **SmartEOB reader's guide PDF**, fetched and verified in full: https://assets.humana.com/is/content/humana/SmartEOBGuidepdf — explicitly documents 3 sections: (1) Medical/dental claims page — claim number, service/process dates, provider, codes, **"Your share"** row; (2) Prescription claims page; (3) **"Plan page" — "Total dollars you've spent this year," "Deductible and maximum out-of-pocket," "Clear view of who paid what for the entire plan year."** This "Plan page" is the single best-documented example of a payer showing the plan-year-to-date deductible/OOP accumulator in black and white.

### 2.9 Medicare's equivalent(s) — two different documents, don't conflate them

Medicare actually has **two** distinct "EOB-like" documents depending on which part of Medicare paid:

- **Medicare Summary Notice (MSN)** — for Original Medicare Part A/B, mailed/e-mailed quarterly. CMS's own annotated sample, fetched and verified in full (Part A version, "Jennifer Washington," numbered callouts 1–7 per page): https://www.cms.gov/medicare/medicare-general-information/msn/downloads/sample-part-a-medicare-summary-notice.pdf
  Confirmed unique-to-Medicare fields not seen on commercial EOBs: **"Your Deductible Status"** ("You have now met your $1,184.00 deductible for inpatient hospital services for the benefit period that began May 27, 2020"), **benefit periods and benefit days used/remaining** (Medicare Part A doesn't use a calendar-year deductible — it resets per "benefit period," a very different accumulator logic Tyndale must model separately from commercial plans), **"Total You May Be Billed,"** and a built-in appeals form with a 120-day deadline. Every page carries **"THIS IS NOT A BILL"** in caps.
  CMS's MSN program overview page: https://www.cms.gov/medicare/coverage/summary-notice
- **Part D "Explanation of Benefits"** — a genuinely separate, monthly document mailed by the beneficiary's Medicare Prescription Drug Plan, distinct from the MSN. Fetched and verified: https://www.medicare.gov/basics/forms-publications-mailings/mailings/costs-and-coverage/explanation-of-benefits — note this page explicitly states **"Download a sample: Not available at this time"**, so ⚠️ flag: Medicare.gov itself does not currently publish a public sample image of this specific document (as of this fetch). Use the MSN sample above as the primary Medicare artifact for the app, and describe the Part D EOB as a distinct, real, monthly document without a public sample to screenshot.

---

## 3. Itemized hospital bill vs. summary statement

### 3.1 Mayo Clinic's own official sample — the best real-world find in this whole memo

Fetched and verified in full. Mayo Clinic publishes an actual annotated sample titled **"Understanding Your Itemized Statement of Charges"** with a mock patient ("Mr John Doe"), real-format CPT/HCPCS codes, and a built-in glossary:
https://www.mayoclinic.org/documents/understanding-your-itemized-statement-of-charges-pdf/doc-20078974

Confirmed content:
- Column headers: **Date of Service | Service Code | Service Description | Amount.**
- Real sample line items: `01/02/05 | G0001 | VENIPUNCTURE SVC-OUTPATIENT | 15.50`; `01/02/05 | 84132 | POTASSIUM, PLASMA | 24.00`; `01/02/05 | 99215-77 | COMPREHENSIVE HISTORY & EXAM – CARDIOVASC. | 124.15`; `01/03/05 | 99214 | DETAIL FOLLOW-UP REPORT VISIT – CARDIOVASC. | 83.65`; **TOTAL CHARGES 247.30**; plus a separate line for **"DIAGNOSIS CODE(S) FOR INSURANCE COMPANY USE."**
- Explicitly states: *"This Itemized Statement of Charges is for your information only. You will be receiving a Monthly Statement of Account (your bill) reflecting your financial responsibility."* — this is the clearest real-world confirmation that **the itemized statement and the actual bill are two different documents**, exactly the distinction Tyndale needs to teach users.
- Mayo's own glossary in the same PDF defines: Billing Account Number, Coordination of Benefits, Diagnosis Code, **Explanation of Benefits** ("provided to the insured by the insurance company"), CMS-1500 (professional claim form), **Itemized Statement of Charges** ("details services provided... a separate itemized statement is provided by each facility... hospital statement will outline charges for room, meals, nursing care, laboratory services and facility fees" — confirming that for one hospital stay you should expect *multiple* itemized statements from *multiple* billing entities), Mayo Clinic Number, Medicare Summary Notice, **Monthly Statement of Account** ("This is the Mayo Clinic bill"), Service Code, **UB04** (institutional/hospital claim form), Visit Number.

### 3.2 State consumer-protection guide on the right to an itemized bill

Fetched and verified: **Georgia Attorney General's Consumer Protection Division**, "Hospital Billing Practices": https://consumer.georgia.gov/consumer-topics/hospital-billing-practices
- Cites the actual statute: *"According to the Georgia Fair Business Practices Act [O.C.G.A. Section 10-1-393(b)(14)], a hospital or long-term care facility has six business days after you have been released from its care as an inpatient to provide you an itemized statement of all charges for which you are being billed."*
- Also flags the real-world pattern that matters for a bill-audit app: *"Even though you may have had only one hospital visit, you can expect to receive a bill from each provider... hospital itself, emergency department, radiologist, admitting physician, consulting physician, anesthesiologist"* — and gives concrete error categories to check: wrong length of stay/room type, duplicate billings across inpatient/outpatient bills, "phantom charges" for standard-admission test panels you refused, **"unbundling"** (billing steps of one procedure separately), and charges for unused supply kits.
- Note this right/timeline is **state law and varies** — Georgia's is 6 business days; this is not a universal federal number. Other states (and CMS guidance generally) frame it as "within 30 days of request" rather than a fixed post-discharge deadline. Confirm state-by-state before hardcoding a number in-app.

### 3.3 Federal hub for bill-rights guidance generally

- CMS "Medical Bill Rights" hub (real, canonical — I fetched a page one level below this hub, https://www.cms.gov/initiatives/your-patient-rights/medical-bill-rights/..., confirming this parent URL is live): https://www.cms.gov/medical-bill-rights and its guides index https://www.cms.gov/medical-bill-rights/help/guides
- Minnesota Attorney General "Medical Billing Pointers" (found via search, real ag.state.mn.us domain): https://www.ag.state.mn.us/consumer/publications/MedicalBillingPointers.asp ⚠️ UNVERIFIED (not opened this session).
- HFMA's "Patient Friendly Billing" report, the industry-standard framework hospitals cite when redesigning statements (found via search, real hfma.org domain, PDF): https://www.hfma.org/wp-content/uploads/2022/10/5177.pdf ⚠️ UNVERIFIED (not opened this session — treat as a lead for design language like "patient-friendly," not yet confirmed to contain a literal sample image).

### 3.4 How a patient requests an itemized bill (typical wording, synthesized from the verified sources above)

Call the hospital's patient financial services / billing office (number is on the summary statement), give the account number and date(s) of service, and use the word **"itemized"** explicitly — ask for "a complete itemized statement, not a summary," specifying you want every CPT/HCPCS code, description, quantity, date, and per-line charge. Follow up in writing/portal message if a copy doesn't arrive. Mayo's own document shows this is routinely available as a standard, named artifact ("Itemized Statement of Charges") separate from the bill itself — it is not an unusual or adversarial request.

---

## 4. Insurance ID card

### 4.1 Industry standard for what belongs on a card: CARIN Alliance / HL7 FHIR "Digital Insurance Card" Implementation Guide

This is the real, canonical, cross-payer standard (built by the CARIN Alliance's Health Plan workgroup with major insurers at the table) for exactly which data elements appear on a member ID card, physical or digital.

- Home: https://hl7.org/fhir/us/insurance-card/
- General Guidance page, fetched and verified in full: https://hl7.org/fhir/us/insurance-card/General_Guidance.html — defines the "Digital Insurance Card" as a **SMART Health Card** (a signed, scannable credential) that a payer "SHALL generate," containing Coverage, Organization, and Patient FHIR resources, shareable via a QR code / SMART Health Link.
- Physical Insurance Card Data Elements page exists at https://hl7.org/fhir/us/insurance-card/Physical_Insurance_Card_Data_Elements.html — ⚠️ UNVERIFIED this session (the fetch timed out); the page is real (linked directly from the verified General Guidance page's own nav) and is exactly the CARIN table mapping physical-card fields (Member ID, Group Number, Payer ID, RxBIN/PCN/RxGrp, etc.) to FHIR fields — worth a follow-up fetch before publishing exact field names from it.

### 4.2 UnitedHealthcare's own consumer page — real, verified, and closest to "annotate this"

Fetched and verified in full: https://www.uhc.com/member-resources/your-member-id-card
Confirms the card commonly includes: **Member**, **Dependents**, **Member ID number**, **Group number**, Primary Care Provider (PCP) if the plan requires one, **Copay, deductible, and out-of-pocket maximum**, network name, whether referrals are required, pharmacy benefits info, and (for Medicare members) "Medicare limiting charges apply." Back of card: member website + customer service phone, nurse line, behavioral health line, and separate provider/pharmacist claims-submission contacts. UHC also links a real sample-card image directly from this page (card-both-1564x544.jpeg, embedded in the fetched HTML).

### 4.3 Blue Cross Blue Shield of Michigan — the most granular real example found

Fetched and verified in full (2026 provider-facing brochure, but it reproduces the actual member-facing card layouts field-by-field, including redacted-format sample numbers): https://www.bcbsm.com/amslibs/content/dam/public/providers/documents/2026/bcbsm-member-id-card-brochure.pdf

Confirmed standard BCBS-Michigan card fields: **Subscriber Name**, **Subscriber ID** (3-character Blue Cross prefix + issued contract number — "use this number for billing and checking eligibility and benefits"), **Issuer** (identifies the specific Blue plan, e.g. "(80840)"), **Group Number**, **Deductible and Out-of-Pocket Max** printed directly on some cards (in/out, with individual/family splits shown as paired dollar figures), a BlueCard® suitcase logo (national network access while traveling), Rx symbol, and on the back: customer service, fraud-report line, precertification fax, behavioral health line, and mailing address for pharmacy claims. Medicare Advantage variants of the same card add **RxBIN**, **RxPCN**, **RxGrp**, and an "Issued MM/YYYY" field.

### 4.4 Pharmacy-benefit fields (RxBIN / RxPCN / RxGrp) — confirmed via the BCBSM PDF above and cross-checked by search

- **RxBIN** ("Bank Identification Number," 6 digits) tells the pharmacy which claims processor to bill.
- **RxPCN** ("Processor Control Number") is a secondary routing identifier within that processor.
- **RxGrp** identifies the specific prescription benefit group/plan.
Real example values seen directly in the fetched BCBSM PDF: `RxBIN: 610011`, `RxPCN: CTRXMEDD`, `RxGrp: BCBSMAN`.

### 4.5 Gaps to flag

- BCBS Texas maintains both a public "Understanding Your Member ID" consumer page (https://www.bcbstx.com/ut/get-help/member-id) and a provider-facing "ID Card Samples" gallery (https://plans.bcbstx.com/provider/training/id_card_samples.html) — both are real, indexed URLs, but **both returned empty/JS-rendered content when fetched this session** ⚠️ UNVERIFIED. Worth a browser-rendered re-check since the samples gallery in particular sounds like exactly the asset Tyndale wants.
- Aetna's own "Find My Member ID" page (found via search, real aetna.com domain) was not opened this session: https://www.aetna.com/individuals-families/member-welcome-guide/find-my-id.html ⚠️ UNVERIFIED.

---

## 5. Where "deductible met so far" and "out-of-pocket spent so far" live in each payer's portal

Important methodological note: these are **secure, logged-in member portals** — I cannot log in as a real member, so every claim below is grounded in **the payer's own public marketing/help page describing that portal's features**, not a screenshot of a live logged-in screen. I've fetched and quoted the payer's own language wherever possible and flagged ⚠️ where I'm relying on a search-result summary instead of a direct fetch.

| Payer | Verified navigation / screen name | Individual vs. family? | "Met" vs. "remaining"? | Source |
|---|---|---|---|---|
| **UnitedHealthcare** (myuhc.com) | Sign in → **"Check your benefits and coverage"** → "Find copay and coinsurance amounts, **view plan spending**..."; separately, **"Claims & Accounts"** is the section name that appears in UHC's own indexed portal URL structure. | Not explicitly split out in the verified marketing copy (fetched page describes "deductible and out-of-pocket maximum information" generally). | "view plan spending," i.e., spent-to-date framing confirmed. | Fetched, verified: https://www.uhc.com/member-resources/myuhc-member-website. The literal "Claims & Accounts" page title was seen in search indexing of `prod.member.myuhc.com/content/myuhc/en/secure/claims-account.html` ⚠️ UNVERIFIED (behind login, not fetched). |
| **Aetna** (member website / Aetna Health℠ app) | Mega-menu item **"Check my benefits"** (links to `health.aetna.com/benefits/medical-plan-summary`, seen directly in the fetched page's own navigation markup) and on-page copy: *"Check coverage and costs — Learn what your health care costs and how much your plan covers. **Not sure if you've met your deductible? You can track spending, too.**"* App video transcript: *"Tap into tools to **track all spending, deductible and claims details**."* | Aetna's separate EOB Guide PDF (Section 2.3 above) explicitly names **both**: "the remaining amount you have to pay in order to meet your yearly **in-network family or individual deductible**." | Both "met" progress and "remaining" amount confirmed via the EOB Guide language. | Fetched, verified: https://www.aetna.com/individuals-families/using-your-aetna-benefits/secure-member-account.html |
| **Cigna** (myCigna) | Homepage dashboard with **deductible progress bars**; official myCigna guide page exists at cigna.com. | Search-summarized as showing "how much of your deductible remains" — not independently confirmed which split (individual/family) displays by default. ⚠️ | "Remaining" framing confirmed by multiple independent search summaries (progress-bar language), consistent with Cigna's own knowledge-center EOB page (fetched, verified) which states EOBs show **"how much of your out-of-pocket medical costs count toward your annual deductible."** | https://www.cigna.com/individuals-families/member-guide/mycigna ⚠️ UNVERIFIED (not fetched this session — page likely JS-rendered); supporting quote from fetched page: https://www.cigna.com/knowledge-center/explanation-of-benefits |
| **Anthem / Elevance** | Mega-menu items **"Check Your Benefits"** and **"Submit Or Track A Claim"** — both seen verbatim in Anthem's own fetched page navigation. Anthem's claims page confirms: *"The claims processor also verifies... how much of your annual deductible and out-of-pocket maximum you've already paid."* | Not confirmed in the fetched copy. ⚠️ | "already paid" (met-to-date) framing confirmed. | Fetched, verified: https://www.anthem.com/member-resources/claims |
| **Blue Cross Blue Shield** — cleanest verified example is the **Federal Employee Program (FEP Blue / MyBlue®)**, which names the exact screen: **"Financial Dashboard."** | Log in to MyBlue → **Financial Dashboard**: *"Deductibles, so you can see how close you are to meeting your deductible... Out-of-pocket costs, including your progress toward your maximum... Your year-to-date summary..."* | Not split out in the fetched copy (FEP is largely self+family enrollment tiers rather than embedded individual/family accumulators). ⚠️ | Explicit "progress toward" (remaining) framing. | Fetched, verified: https://www.fepblue.org/manage-your-health/manage-claims-records/financial-dashboard |
| BCBS state plans use **"Blue Access for Members"** as the portal brand (confirmed name via search across TX/IL/OK/NM/MT sites) with an on-dashboard **"out-of-pocket spending summary"** and a **"Claims"** button. | Individual/family split not independently confirmed. ⚠️ | "spending summary" framing per search summaries. | ⚠️ UNVERIFIED by direct fetch this session: https://www.bcbstx.com/medicare/member/blue-access-for-members (and IL/OK/NM/MT equivalents at the same path pattern). |
| **Kaiser Permanente** (kp.org) | Kaiser's own cost-estimator tools state they use *"your actual health plan details, including **your remaining deductible and out-of-pocket costs for the year**"* once signed in. | Not confirmed. ⚠️ | "Remaining" framing confirmed directly in Kaiser's own fetched text. | Fetched, verified (tool descriptions embedded in this page): https://healthy.kaiserpermanente.org/learn/understand-health-plan-documents (links to the actual calculator and to https://healthy.kaiserpermanente.org/support/estimating-your-costs) |
| **Humana** (MyHumana) | Confirmed via Humana's own SmartEOB Guide PDF: the EOB itself has a dedicated **"Plan page"** showing *"Total dollars you've spent this year," "Deductible and maximum out-of-pocket," "Clear view of who paid what for the entire plan year."* The MyHumana portal/app is described (via search) as showing "deductibles and balances" and a claims dashboard, consistent with this. | Not confirmed. ⚠️ | Spent-to-date ("you've spent this year") framing confirmed directly from Humana's own PDF. | Fetched, verified: https://assets.humana.com/is/content/humana/SmartEOBGuidepdf |
| **Medicare.gov / MyMedicare.gov** | The MSN itself (Section 2.9) has a dedicated **"Your Deductible Status"** box on page 1: *"You have now met your $1,184.00 deductible... for the benefit period that began May 27, 2020."* Medicare.gov's claim-status page is the portal path (https://www.medicare.gov/providers-services/claims-appeals-complaints/claims/check-status). | **N/A — Medicare Part A/B has no family accumulator; it is per-beneficiary**, and Part A uses **"benefit periods,"** not a calendar-year deductible — a structurally different accumulator than every commercial plan above. This distinction is important enough to call out as its own UI state in Tyndale. | "Met" framing confirmed directly in the fetched MSN sample. Caveat found via search (not independently verified against a live account): your online Medicare account reportedly shows deductible-met status but does **not** reconcile it against what you personally paid — cross-referencing actual payments still requires manual review of claims. ⚠️ | MSN fetched, verified: https://www.cms.gov/medicare/medicare-general-information/msn/downloads/sample-part-a-medicare-summary-notice.pdf. Claim-status page ⚠️ UNVERIFIED by direct fetch: https://www.medicare.gov/providers-services/claims-appeals-complaints/claims/check-status |

---

## 6. The timing problem: why "deductible met" must be read as-of the date of service, not as-of today

### 6.1 The plain-English explanation

A deductible/out-of-pocket **accumulator** is a running total the payer keeps for a plan year, incremented claim-by-claim as claims finish processing. Two structural facts make this messy for a bill audit:

1. **Claims do not process in date-of-service order.** A visit from January might not finish adjudicating until March, while a February visit clears in two weeks. The accumulator is updated in *processing* order, not *service* order. If you check "deductible met" today, you're seeing the total *as of every claim processed so far* — which is not the same as "the total that had accumulated on the actual date the bill you're auditing was incurred."
2. **The accumulator keeps moving after the fact.** Every claim that finishes processing *after* your date of service — even for care that happened earlier or later — changes the running total. So the "deductible met" figure you see in the portal *today* reflects claims that may postdate the visit you're trying to audit. To correctly judge whether a specific bill's cost-sharing was calculated correctly, you need to know **what the accumulator actually was on that specific date of service**, which the portal's live "today" number will not tell you directly once time has passed and more claims have posted.

### 6.2 Why gathering every EOB from Jan 1 → date-of-service solves it

Because each EOB shows (a) the date of service, (b) the dollar amount applied to the deductible for that specific claim, and (c) the running "you may owe" figure for that claim, a user (or Tyndale) can **manually reconstruct the accumulator at any point in time** by sorting every EOB issued for the plan year by date of service (not by mail date or processed date) and summing the deductible-applied and coinsurance/OOP-applied amounts up to the date in question. This is exactly the "recompute the accumulator" workflow the audit tool needs, and it's why the memo emphasizes collecting *all* EOBs for the plan year, not just the one tied to the disputed bill.

### 6.3 Real-world corroboration that this is a known, documented failure mode — not a hypothetical

A directly on-point (though commercial, not governmental) explainer lays out this exact mechanic in detail, including the correct remediation rule:

> **"Claims Processed Out of Order** — If Claim B (March) processes before Claim A (January), the system may calculate your deductible incorrectly. Claim B might show full deductible responsibility when, chronologically, Claim A should have satisfied part of it first."
>
> **"Billing Lag: The Cross-Year Trap** — you had a procedure in November, met your deductible for the year, and then in February the bill arrives. Your insurer processes it and applies the cost to your NEW plan year deductible because the claim crossed into the next calendar year... **The Rule That Protects You: Date of service controls, not date of processing.** Insurance must apply claims to the plan year in which the service was rendered."
>
> Recommended fix script: *"I need claims [number] and [number] reprocessed in date-of-service order because the current processing sequence resulted in incorrect deductible allocation."*

Source (fetched, verified in full — commercial patient-advocacy company, not an official payer/CMS page, cite accordingly in-app): https://www.careroute.ai/blog/met-deductible-still-getting-bills

This same source is also useful for a secondary, adjacent failure mode worth building into Tyndale: **split accumulators** (in-network vs. out-of-network deductibles are tracked completely separately; some plans carve out a separate pharmacy deductible; family plans may be "embedded" — each member has their own individual deductible inside the family total — or "non-embedded"/aggregate, where the full family deductible must be met before the plan pays for *anyone*). A companion piece on the same domain covers copay-accumulator programs specifically (manufacturer copay-card dollars not counting toward the deductible) — ⚠️ UNVERIFIED, only referenced from within the page I did fetch, not opened directly: https://www.careroute.ai/blog/copay-accumulator-trap

### 6.4 Official grounding for the underlying concepts (deductible, plan year, reset)

- HealthCare.gov glossary, "Deductible" — fetched, verified: https://www.healthcare.gov/glossary/deductible/ — *"The amount you pay for covered health care services before your insurance plan starts to pay... Family plans often have both an individual deductible, which applies to each person, and a family deductible, which applies to all family members."*
- HealthCare.gov glossary, "Plan year" — fetched, verified: https://www.healthcare.gov/glossary/plan-year/ — *"A 12-month period of benefits coverage under a group health plan. This 12-month period may not be the same as the calendar year... For individual health insurance policies this 12-month period is called a 'policy year.'"* This is the official confirmation that "Jan 1 → date of service" is only the right window for calendar-year plans — for a July–June plan year, the correct window is "plan-year start → date of service," which Tyndale should ask the user to confirm rather than assume January 1.
- Medicare's structurally different version of the same concept — **benefit periods**, not a plan year — is confirmed directly in the fetched MSN sample (Section 2.9): a new Part A benefit period (and new $1,184-type deductible) starts after 60 consecutive days with no inpatient/SNF care, which can happen *multiple times within one calendar year*. This is a materially different accumulator model than every commercial plan in Section 5 and should get its own explanation screen in-app rather than being folded into the generic "plan year" logic.

---

# THE ANNOTATION SPEC

For each document type, the 4–6 labeled callouts the app should draw on an illustrative (blank/sample, non-PHI) example so a user knows exactly what to look for. Numbering matches a natural top-to-bottom or left-to-right reading order on the real documents cited above.

## A. Summary of Benefits and Coverage (SBC)
*Base image: recreate CMS's own Sample Completed SBC layout (Section 1.2).*
1. **Coverage Period & Plan Type banner** (top) — confirms this SBC matches the plan year and plan (PPO/HMO/EPO) actually being audited; wrong plan year = wrong numbers.
2. **"What is the overall deductible?" row** — the headline individual/family deductible dollar figures.
3. **"Are there other deductibles for specific services?" row** — flags hidden sub-deductibles (e.g., separate $300 Rx or therapy deductible) that a naive audit would miss.
4. **"What is the out-of-pocket limit?" row** — separate network vs. out-of-network OOP max figures.
5. **Network vs. Out-of-Network "What You Will Pay" columns** in the Common Medical Event grid — the side-by-side copay/coinsurance comparison for the specific service category on the bill being audited.
6. **"Coverage Examples" page** — sanity-check tool: if a user's real bill's cost-sharing looks wildly different from the comparable coverage example, that's a signal to dig further.

## B. Explanation of Benefits (EOB)
*Base image: recreate CMS's own generic sample EOB (Section 2.1), which already has 8 official callouts — condensed here to the 6 most load-bearing for a bill audit.*
1. **Claim Number & Date of Service** — the join key between this EOB and the itemized bill/statement being audited.
2. **Provider Charges (billed amount)** — what the provider asked for.
3. **Allowed Charges (allowed amount)** — the negotiated/contracted rate; this is the number that actually matters, not the billed charge.
4. **Deductible / Coinsurance / Co-Pay columns** — exactly how the allowed amount was split between plan and patient, and how much of it hit the deductible.
5. **Paid by Insurer** — what the plan actually sent the provider.
6. **What You Owe / Patient Responsibility** — the number that should match the final provider bill; if the provider bill is higher than this figure, that's the core audit finding.

## C. Itemized Hospital Bill / Patient Statement
*Base image: recreate Mayo Clinic's own "Understanding Your Itemized Statement of Charges" layout (Section 3.1).*
1. **Patient/Account/Visit identifiers** (Mayo Clinic Number, Visit Number, Dates of Service) — confirms this itemized statement matches the claim/EOB being cross-checked.
2. **Date of Service column (per line)** — each service's own date, not just the overall visit range; catches charges for days you weren't there.
3. **Service Code (CPT/HCPCS) column** — the exact code billed for each line; this is what lets a user look up whether the code matches what actually happened.
4. **Service Description column** — plain-language description paired with the code; mismatches here (code vs. description) are a red flag.
5. **Amount column (per line) + Total Charges** — individual line charges and the sum; compare against the "Provider Charges" total on the corresponding EOB.
6. **"This is for your information only — a separate [Monthly] Statement of Account is your bill" disclaimer** — the single most important callout, since it's the exact point of confusion the itemized-vs-summary distinction exists to resolve.

## D. Insurance ID Card
*Base image: recreate UHC's and BCBS-Michigan's confirmed field sets (Sections 4.2–4.4).*
1. **Member Name & Member ID number** — the primary identifier to match against every EOB/bill (note: "member" = subscriber, may differ from "patient" on a family plan).
2. **Group Number / Issuer** — identifies the specific employer group and Blue-plan/issuer, needed when calling customer service or verifying eligibility.
3. **Plan Type / Network name (PPO/HMO/EPO)** — determines whether out-of-network care is covered at all (relevant to which SBC row applies).
4. **Printed Copay / Deductible / OOP figures (if present)** — a quick cross-check against the SBC, though the card's numbers are abbreviated and the SBC/EOC is authoritative if they conflict.
5. **RxBIN / RxPCN / RxGrp** — pharmacy-specific routing numbers, separate from the medical Member ID; needed for prescription-drug bill audits specifically.
6. **Back-of-card customer service / claims-submission phone numbers** — where to call to request the SPD/EOC or dispute a claim.

## E. Payer Portal — "Deductible Met" / "Out-of-Pocket Spent" Screen
*Base image: composite of the FEP Blue "Financial Dashboard" (Section 5) and Humana's SmartEOB "Plan page" (Section 2.8/5), both independently verified with this exact content.*
1. **"As of" / statement date** — the single most important callout per Section 6: this figure is a snapshot, not a live truth for past dates.
2. **Deductible progress (met vs. remaining)** — individual figure.
3. **Deductible progress — family figure (if applicable)**, and whether the plan is embedded or aggregate (Section 6.3).
4. **Out-of-pocket max progress (met vs. remaining)** — separate from the deductible; note in-network vs. out-of-network are almost always tracked as two separate accumulators.
5. **Year-to-date claims list feeding the total** — the underlying claims (with dates of service) that sum to the headline number; this is what a user needs to export/screenshot to let Tyndale recompute the accumulator as of a different date.
6. **Plan year start date** — needed to know whether "Jan 1" is actually the right starting point for recomputation (Section 6.4) — many plans run non-calendar plan years.

---

## Six-bullet summary (for the calling agent's final message)

- Wrote the full memo to the exact requested path: `/Users/brock/Library/Application Support/Claude/local-agent-mode-sessions/0d67fee1-df5f-4cfa-a7e5-e233d2ae33c6/201e389a-a465-4f5a-91b3-86b12f7a5c14/local_835de7cb-96b8-473f-9ef3-717919411ca1/outputs/_raw_example_documents.md`.
- **SBC**: pulled and fully quoted CMS's live "Sample Completed SBC" PDF (5 pages, current as of Jan 2025 publication) plus the blank DOL/CMS template, and used Kaiser's own page to nail the SBC-vs-Schedule-of-Benefits/EOC distinction the task asked about.
- **EOB**: got verified, fetched samples/guides directly from CMS (generic + Medicare MSN), UnitedHealthcare, Aetna, Cigna, Blue Cross NC, Kaiser, and Humana (Humana's SmartEOB sample + reader's guide PDFs were the richest find); Anthem and several other BCBS licensees only have third-party or unfetchable pages, flagged ⚠️.
- **Itemized bill**: Mayo Clinic's own "Understanding Your Itemized Statement of Charges" PDF is a genuine, real, CPT-coded sample with a built-in glossary — the best single artifact in the memo — paired with a Georgia AG consumer-rights page citing the actual statute.
- **ID card & portals**: verified UHC's and BCBS-Michigan's own field-level documentation for ID cards, and FEP Blue's "Financial Dashboard" plus Humana's SmartEOB "Plan page" for exactly how deductible-met/OOP-spent is displayed; several payer-specific portal pages (BCBS Texas/Illinois, Cigna, Kaiser's exact screen name) could only be partially confirmed and are flagged ⚠️ for a follow-up browser-based check.
- **Timing problem**: documented the accumulator/claims-out-of-order/cross-plan-year mechanics against HealthCare.gov's official "deductible" and "plan year" glossary definitions, plus a detailed (commercial, clearly labeled as such) explainer that independently confirms the exact failure mode — including the "date of service controls, not date of processing" remediation rule — that justifies Tyndale's "gather every EOB for the plan year" approach.
- Every citation in the memo is a real URL; anything I could not personally open and confirm this session is explicitly marked **⚠️ UNVERIFIED** inline, with a note on why (login wall, JS rendering, or fetch timeout) so it's a clear follow-up list rather than a silent gap.
