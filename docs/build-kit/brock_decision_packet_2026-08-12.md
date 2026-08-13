# Decision packet for Brock — 2026-08-12

**Answer inline; every item is decision-or-source, never a request to write from scratch — drafts exist where drafting was possible.** Companion drafts: `33_orchestration_script_v2_DRAFT.md` (copy) · `37_x_rules_contracts_DRAFT.md` (X2/X3/X5) · annotated `docs/design/round2_delta_inventory.md` (keep/drop). Nothing in the drafts renders until you approve.

---

## A · Sign-offs (approve / edit / reject — drafts ready)

| # | Item | Where |
|---|---|---|
| A1 | **§10.2 no-base-rate variant** (`decline.guarantee_trio_no_rate`) — the launch-default guarantee decline | v2 draft §10.2-alt |
| A2 | **Eleven unauthored keys** — all drafted in your voice; per key: approve, edit, or "delete the beat" | v2 draft §§2.4, 4.5–4.6, 9.6–9.11, 10.1-cont |
| A3 | **`{itemized_request_script}`** — the §5.2 ask-words | v2 draft §5 |
| A4 | **Wrong-doc: one string or four?** Four branch variants drafted (Option B); Option A = your single §5.3 stands | v2 draft §5.3a–d |
| A5 | **SUD edge prompt** — F2 (checklist) and §3 (script) disagree; a draft exists if "author" wins, else amend F2 | v2 draft §3.6 |
| A6 | **X2/X3/X5 contracts** — esp. the X5 `error_type` enum (14 proposed types + escape hatch) and the two open questions at the bottom of the draft | 37 draft |
| A7 | **Delta inventory recommendations** — 16 keep / 3 drop / 8 defer / your 4 conflicts (C1–C4) + N7 glassmorphism | inventory annotations |

## B · Decisions only you can make (no drafts, by design)

| # | Decision | The tension |
|---|---|---|
| B1 | **Crisis routing** — §10.5 ("I can share a few resources") vs locked DL-04 clean-refusal-no-routing. The clean decline still ships; your copy is registered, unwired. | Both can't govern. If §10.5 wins, DL-04 gets amended deliberately and counsel should see it — a safety-surface change deserves the full treatment. |
| B2 | **$504,100 "recovered for members"** — live on the landing (B4 requires it). Substantiated? As of when? What updates it? | A public dollar figure for a pre-launch product, next to your own "we're early" beta band. The analytics substantiation-file machinery exists — this number should have one. |
| B3 | **Headline** — checklist B1 ("Medical bills are full of errors…") shipped; prototype's "Your medical bill is probably wrong" lost. Confirm or swap. | The prototype's version asserts a claim about the reader's specific bill with no support. |
| B4 | **CTA** — prototype's "Check my bill — free" shipped over checklist's "Check my bill". Confirm. | "free" is accurate today and stays accurate under the locked free-audit model. |
| B5 | **`[B]` tag assignments** — name which keys are `[B]` (your 4 marks are dual `[A]/[B]`, so enforcement parses zero). §6.3 finding-cards and §12.1 handoff are the candidates; naming one turns citation-chip enforcement on. | Until then "never uncited" is doctrine without teeth. |
| B6 | **A8 body size in the app** — mobile body is 14px vs your ≥16px floor; changing reflows every screen. Round-2 scope or its own pass? | Recommend: own pass, straight after the delta application session. |

## C · Sourcing requests (supply the citation or approve dropping — DO NOT ship without)

| # | Claim | Held back? | What's needed |
|---|---|---|---|
| C1 | Four-stat band: **74%** disputed-errors corrected · **19%** denied / <1% appealed · **100M+** in medical debt · **45%** no itemized bill in 30 days | HELD BACK | Per stat: the specific study/report, year, and publisher — "JAMA · KFF" is an attribution, not a citation. Same gate that bans the 80% figure (B11). |
| C2 | **"Use the $400 dispute right"** (tips band) | HELD BACK | This is a Tier-B legal claim (reads like the PPDR $400 threshold). Exact statute/reg cite + the qualifier language you want — or drop the tip. |
| C3 | Tips band as a whole | HELD BACK | It's a subscription tease while billing is dark. Ship as tease, or hold until billing is live? |
| C4 | "What brings you in today?" chooser → `/estimate`, `/find-doctor`, `/plan-visit` | HELD BACK | Post-core surfaces. Omit the chooser, or point everything at `/upload` for now? |

## D · Small confirms (one word each)
D1 UnitedHealthcare named in the illustrative Record card on a public page — fine or genericize? · D2 `sob-example.png` — upload flow asset? · D3 Hero photo behind the navy→teal gradient under a scrim (A3 preserved) — intended? · D4 Landing body promoted 15→16px per A8 — confirm floor. · D5 Zero-gap landing example — no clean-bill copy exists; confirm the card simply never shows one.

---
*Process note: approved copy returns as **v2 of `33_orchestration_script.md`** (the registry is drift-guarded against direct edits). Decisions from §B become DL entries verbatim. Anything unanswered stays open — nothing here gets guessed.*
