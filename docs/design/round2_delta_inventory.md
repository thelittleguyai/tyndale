# Round-2 app delta inventory

**What this is:** a screen-by-screen diff between Brock's round-2 prototype
(`docs/design/prototype-round2/`, reference only — never imported or built) and the shipped
member app (`apps/mobile`). **Status 2026-08-17: the 16 KEEP rows are applied** (see per-row notes); the 4 conflicts,
N7 glass, N3, N6, N8, L4 and T5 stay HELD for Brock per the packet.

**Method:** read the prototype component, read our counterpart, record each visible or
behavioural difference. Sorted by classification, then by screen.

**Classification**
| | meaning | cost |
|---|---|---|
| `[token]` | styling expressible in the existing token system | cheap |
| `[layout]` | structural change to a component we already have | moderate |
| `[new]` | a pattern or surface we don't have at all | build |
| `[behavior]` | a UX behaviour difference | varies — read each |
| `[conflict]` | contradicts a locked decision or the checklist | **needs Brock** |

**Totals:** 6 `[token]` · 7 `[layout]` · 8 `[new]` · 5 `[behavior]` · 4 `[conflict]`

---

## `[conflict]` — needs Brock before anyone builds

| # | Screen | Prototype | Ours | Note |
|---|---|---|---|---|
| C1 | Upload | "**No EOBs needed.** With these details I'll pull your Explanation of Benefits from Blue Shield automatically. If their system won't give them to me, I'll ask you — and that's the only time I will." | Uploads-first: we ask for the EOB, and the needs-documents checklist chases it | **DO-NOT-ADOPT-YET.** This copy promises automatic EOB retrieval, which is the coverage-connection (1upHealth/FHIR) path — Full V1, post-launch, and currently behind `enable_coverage_connection=false` with an in-memory token store. Shipping it at V1-Lite would promise a capability that does not exist and would make the *correct* uploads-first ask read as a failure. The whole upload flow's information architecture changes if this lands, so it gates C2/C3 below. |
| C2 | Verification | "No" maps to `bg-severity-high` (a red/alarm token) | "No" is a neutral choice among three | A "no" answer is **information, not an error** — the user did nothing wrong by telling us a charge is wrong. Colouring it as high severity teaches people that honesty is a failure state. Recommend keeping neutral; needs his call since it's his prototype. |
| C3 | Findings | Impact renders as `−$389.00` in money green | We render the impact without a leading minus | A minus reads as "you lose $389". The finding is worth **+$389 to the user**. Sign convention needs a decision — it appears on every finding card. |
| C4 | Three numbers | Prototype three-numbers card has no zero-gap variant | Our reveal suppresses the gap callout when the gap is ≤0 (E3, shipped) | The prototype assumes a gap always exists. Confirm the clean-bill case renders the three numbers with **no** callout (what we do today) rather than a "$0.00 less" line. |

---

## `[behavior]`

| # | Screen | Prototype | Ours | Note |
|---|---|---|---|---|
| B1 | Status card | Auto-advances the four stages on a timer (1.6s each), then fires `onComplete` | Stages fill on **real** case-state transitions; no timers, no percentages | Prototype behaviour is a demo affordance only. **Do not adopt** — D2/checklist forbids fabricated progress. Ours is correct; recorded so nobody "fixes" it later. |
| B2 | Upload capture | Live capture shows an edge-detection frame + a "Looks readable" badge, then **Retake / Got it** | Capture state shipped; **badge deliberately not shipped** | **RESOLVED 2026-08-12 — badge dropped, warning kept.** The prototype's badge is unconditional, so it's a claim about a photo nobody checked. We now measure two things for real (longest edge vs the OCR floor; variance-of-Laplacian for focus) and surface them ONLY as a warning when one fails. There is no positive counterpart by design: sharpness is not readability — glare, a cut corner, a thumb over the total all pass and still fail OCR — and a "readable" badge contradicted downstream costs more than it buys. `assessCapture` has no field that could carry a pass, and a test asserts that. Brock's call is logged in the asks doc §3.6. |
| B3 | Findings | Severity tag (`high`/`medium`/`neutral`) on every finding | We carry `finding_type` (payer/provider/encounter) and colour by that | Two different axes. Severity is a user-facing judgement we don't currently compute; adopting it means deciding what sets it. |
| B4 | Action card | Per-step phone number + claim number, tap-to-dial | **DONE 2026-08-12** — typed claim/account/phone fields shipped (migration 0037); the pinned strip carries the party-correct reference and tap-to-dial uses typed numbers only | Closed by the B4 prerequisite session; L7/H6 both PASS in the sweep |
| B5 | Dashboard | A "quick check-in" card surfaces **first** on login | **APPLIED 2026-08-17** — the outcome follow-up now leads the screen, above the metrics (Phil approved proceeding; Brock can still reorder with one move) |

---

## `[new]` — patterns/surfaces we don't have

| # | Screen | Pattern | Note |
|---|---|---|---|
| N1 | Upload | Camera capture with edge-detection framing + looks-good/retake | Checklist C1+C5. **BUILT 2026-08-12 (web).** Camera leads the upload screen, static guide frame, review → Use this photo / Retake, multi-page grouping into one document. Two deliberate departures: **no edge detection** (a static guide, not a tracker — an animated "locking on" overlay would be decoration pretending to be a capability) and **no "Looks readable" badge** (see B2). **Native is blocked on DL-44** — `expo-camera` can't be installed while `react-native-worklets` ERESOLVEs; `isCaptureSupported()` is the one seam to fill. |
| N2 | Thread | `branch-cards`: five authored state cards | **APPLIED (4 of 5) 2026-08-17** — BranchCard renders on the TYPED payload keys (data_quality.kind / wrongdoc_branch / branch_state) with a label chip + one inline action routed to the existing add-a-document path; reconcile is information so it gets no button. Honest-odds (§10.2) is NOT a thread entry today (it renders on the decline path), so its card waits for that plumbing rather than a fake |
| N3 | Gameplan | `action-card`: numbered, collapsible step with a targets-$ badge and inline script | Ours is a step list + separate call mode. Merging them is a real restructure. |
| N4 | Dashboard | Deductible/OOP **meters** (met vs total) | **CORRECTION — already built before this pass.** MetricCard has carried a met/total progress track since the redesign; "Not set" in screenshots is the honest no-data state, not a missing feature. Row was stale when written |
| N5 | Dashboard | Analytics stat cards (recovered, cases, etc.) | **APPLIED (prominence) 2026-08-17** — numerals 26px semibold tabular; the confirmed/estimated split kept exactly as-is per the KEEP note |
| N6 | Dashboard | Action tiles with hover/long-press **tooltips** | Our quick-action tiles have no tooltip layer. |
| N7 | Global | `glass` / `AmbientAuras` / `GlassCard` — a glassmorphism + ambient-gradient visual language | This is the round-2 visual direction. It is **not** expressible in the current token system (it needs blur, layered translucency and gradient auras). Adopting it is a design-system decision, not a component change — probably the single biggest question in this document. |
| N8 | Landing→app | `/estimate`, `/find-doctor`, `/plan-visit` surfaces | Post-core features with placeholder screens in our app. Prototype treats them as live. |

---

## `[layout]`

| # | Screen | Prototype | Ours |
|---|---|---|---|
| L1 | Status card | Header row ("Working on your audit" → "Audit ready") with spinner/check | **APPLIED 2026-08-17** — the two prototype states only; a failed/incomplete terminal gets no header (the rows carry it) rather than copy nobody wrote |
| L2 | Three numbers | Service context line above (`MRI of the left knee · provider · payer`) | **APPLIED (partial) 2026-08-17** — `provider · payer` from TYPED fields only, omitted when unknown. The service description ("MRI of the left knee") is NOT rendered: no typed field carries it and deriving it from line items would be a guess. Found+fixed en route: the E3 gap callout was in the payload but never rendered by the card |
| L3 | Finding card | Title and impact on **one** row, impact right-aligned tabular | **APPLIED 2026-08-17** — sub-case findings list: shared row, right-aligned, tabular numerals |
| L4 | Finding card | Severity tag + citation chip on one meta row under the body | Our source line sits under the claim; no severity tag |
| L5 | Verification | Three large icon+label buttons in a row | **APPLIED 2026-08-17** — check / x / question-mark icons on the shared LineItemCard buttons (thread + classic encounter both) |
| L6 | Case summary | Recovered/identified as prominent stat tiles | **APPLIED 2026-08-17** — tally numerals up a step (26px, tabular); confirmed/estimated hints untouched |
| L7 | Call mode | Pinned claim# + dollar strip | We pin the dollar only (no claim number — see B4/C-list) |

---

## `[token]`

| # | Delta | Note |
|---|---|---|
| T1 | Radii: prototype uses `rounded-2xl`/`3xl` (16–24px) | **APPLIED 2026-08-17** — card 16, moment 24, via the token classes so every consumer moved at once. |
| T2 | `money` green for impacts/CTAs | We now have `money` (#2E7D5B) — **already aligned**, just unused in some spots. |
| T3 | `citation` chip on findings | We have `citation` and now render it (E4). **Aligned.** |
| T4 | `severity-high` / `severity-neutral` tokens | We have `danger`/`warning`; needs a name mapping, not new colours — unless C2 says severity is its own axis. |
| T5 | Display font (`font-display`) for numerals/headings | We use one family throughout. Adding a display face is a token + asset change. |
| T6 | `shadow-soft`/`shadow-float` elevation scale | **APPLIED 2026-08-17** — `soft`/`float` added ALONGSIDE `card`/`elev` (extend, not rename), mirrored in shared tokens. |

---

## Cowork keep/drop recommendations — 2026-08-12 (Brock vetoes; conflicts are HIS call)

**`[conflict]` — recommendations only, Brock decides:**
- **C1: KEEP OURS (do-not-adopt-yet).** Uploads-first until coverage-connection ships; the prototype copy promises a capability that's gated off. Revisit the copy at flip time — it's good copy for that day.
- **C2: KEEP OURS (neutral "No").** Honesty must not look like an alarm. If severity color is wanted anywhere, it belongs on findings (see B3), not on the user's answers.
- **C3: DROP the minus sign; recommend positive framing** — impact renders as the amount with direction in words ("{finding_amount} back in your pocket" is already the script's register). Sign conventions on money are trust surfaces.
- **C4: KEEP OURS (zero-gap suppression).** Confirm and close.

**`[behavior]`:** B1 **DROP** (fabricated progress — recorded as correct, never adopt). B2 **DEFER into N1** — adopt only with a real readability check behind the badge; an optimistic "Looks readable" is a small fabrication. B3 **DEFER pending X5** — if severity ships, derive it mechanically (dollar impact × confidence), never hand-assigned; needs Brock. B4 **KEEP, sequenced** — requires claim#/phone extraction first (data model), then L7/H6 complete. B5 **KEEP** — check-in-first dashboard matches the advocate identity; cheap; Brock confirms priority order.

**`[new]`:** N1 **KEEP (build)** — checklist C1/C5 requires it; largest item; schedule as its own session. N2 **KEEP (cheap)** — presentation over shipped behaviors; high value. N3 **DEFER** — merging gameplan+call mode is a restructure with no conformance driver. N4 **KEEP** — meters from existing accumulator data. N5 **KEEP-partial** — align stat-card prominence, keep our honest confirmed/estimated split. N6 **DROP** — hover tooltips are a desktop idiom; long-press hides meaning on mobile. N7 **DEFER to a named "round 2.5" decision** — glassmorphism/auras change the token vocabulary (blur, translucency, gradients); do not let it ride in via component PRs; needs Brock + a costed token-system extension. N8 **DEFER** — post-core per Brock's own scope.

**`[layout]`:** L1, L2, L3, L5, L6 **KEEP** (cheap, clear improvements). L4 **KEEP the meta-row, HOLD the severity tag** pending B3/X5. L7 **KEEP after B4** lands the claim number.

**`[token]`:** T1 **KEEP** (radii bump). T2/T3 already aligned. T4 **HOLD** pending C2/B3 (severity may not exist as an axis). T5 **KEEP if Brock names the display face** — a font is a brand decision, not an engineering pick. T6 **KEEP** (rename/extend shadows).

**Net if Brock accepts as-is:** 16 keep (mostly cheap), 3 drop, 8 defer with named triggers, 3 his-call conflicts + N7. The application session can start on the KEEP set the day he returns this.

---

## Recorded as already-correct (do not "fix")

Things where we deliberately differ and **ours is right** — listed so a future session doesn't
regress them chasing the prototype:

- **No fabricated progress.** Stage bars fill on real state only (B1 above).
- **Uploads-first.** The EOB is asked for, not promised automatically (C1 above).
- **Zero-gap suppression.** No "$0.00 less than your insurer's number" (C4 above).
- **`[B]` strings never render uncited** — the prototype's citation chip is decorative; ours is
  a rendering *requirement* backed by the degradation path.
- **"Not sure" is honoured, never penalised** — and now says so in-thread (D8).
