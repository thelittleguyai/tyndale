# Engineering review of the Cowork drafts — 2026-08-12

**Read this alongside the three drafts, before answering them.** Cowork produced them from
`COWORK_PROMPT_2026-08-12.md`; this is engineering's check of what it produced, plus the two
places the drafts are already out of date because code shipped the same day.

Reviewed: `33_orchestration_script_v2_DRAFT.md` · `37_x_rules_contracts_DRAFT.md` ·
`brock_decision_packet_2026-08-12.md`.

---

## 1 · The no-invention rule held

The prompt's governing constraint was: draft copy in voice, invent no fact, statistic,
citation, base rate, or dollar figure. **Checked line by line — it holds.**

- `decline.guarantee_trio_no_rate` (§10.2-alt) does the hard thing correctly: it declines to
  quote odds *and says so out loud* ("I won't quote odds I don't have… I'd rather tell you that
  than invent one") rather than reaching for a plausible-sounding rate.
- Every remaining fact-dependent item is in the draft's own "NOT drafted" list: `{base_rate}` /
  `{base_rate_source}`, the §10.5 crisis conflict, the landing statistics, and the `[B]` tag
  assignments. Those are the right four to have refused.
- The X5 `error_type` enum is labelled a PROPOSAL needing Brock's authority, not presented as
  settled. Correct — a taxonomy is a rules decision, not an engineering one.

One nuance worth Brock's eye, below.

## 2 · Two dependency warnings are already stale — B4 shipped today

The v2 draft flags `{claim_number}` as unavailable:

> *"⚠️ Dependency: `{claim_number}` is not yet extracted/stored (delta B4). Until it is, this
> renders the degradation variant — approve the copy anyway and engineering wires the variable."*

**That is no longer true.** Delta B4 shipped in `dbbfa37` (2026-08-12): `claim_number`,
`account_number`, `provider_phone` and `payer_phone` are typed columns on the case, extracted at
parse time and exposed to the registry variable resolver. So:

| Draft key | Variables used | Status now |
|---|---|---|
| §9.6 `call_script_opener_payer` | `{claim_number}` `{patient_name}` `{service_date}` | **all resolve** — renders as written |
| §9.7 `call_script_opener_provider` | `{account_number}` `{patient_name}` `{service_date}` | **all resolve** — renders as written |
| §5 `{itemized_request_script}` | `{account_number}` `{service_date}` | **all resolve** |

Practical effect: **approve these and they render on the next copy drop — no engineering
follow-up, no degradation variant.** Where an individual case genuinely lacks the number (the
document didn't print one), the §5 degradation variant still fires per his §0 rule 2, which is
the intended behaviour and not a gap.

## 3 · One tagging question: the SUD prompt asserts a legal rule as `[A]`

`attest.edge_substance` (draft §3.6) says substance-use treatment records *"carry extra privacy
protection — often even from family."* That is true, and it is a **legal/coverage claim** (the
42 CFR Part 2 regime), which under the voice tiering is Tier **`[B]`** — and a `[B]` string may
only render **with** its citation.

The draft tags it `[A]`. **This is not a Cowork error** — the engineering-written string live in
the product today makes the same assertion with the same tag, so the draft faithfully inherited
it. But since Brock is deciding this key anyway, it's the moment to fix it:

- **`[B]` + a citation** → renders with the citation chip, and the claim is grounded.
- **`[A]` reworded** → drop the rule-assertion and keep only the consequence ("this may need to
  come from {patient_name} directly"), which claims nothing legal.
- **Drop the beat** → amend checklist F2, which is the other half of the F2 ↔ §3 conflict he has
  to resolve regardless.

Engineering has no preference between the three; all are cheap. What we can't do is keep a legal
assertion at `[A]` now that the tier enforcement is live.

## 4 · The X-rules contracts are implementable as drafted

X2, X3 and X5 are written to X1's shape (what must be true · what fails · a worked failing
example) and each carries a machine check that maps onto data we already have — `missing_inputs`
per DL-72/85 for X3, line-item refs for X5. **On sign-off, the three stub checkers can be built
without a second conversation**, which was the point of asking.

The three questions at the bottom of that draft are genuinely blocking and genuinely his: the
enum, whether §5.4's reconciliation counts as `informational_context`, and the tier→qualifier
mapping.

## 5 · What engineering does when each item comes back

| Answer | Engineering action |
|---|---|
| Copy approved (any subset) | Drops in as a new version of `33_orchestration_script.md`; the drift guard then holds it verbatim |
| X2/X3/X5 signed off | Replace the three `NotImplementedError` stubs with real checkers; they start failing CI on violations |
| Delta keep/drop returned | The application session can start on the KEEP set |
| SUD tagging decided | One-line change either way |

Nothing in the drafts is blocked on engineering. Everything is blocked on Brock.
