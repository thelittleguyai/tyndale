// The reviewer's in-progress verdict, as plain data + pure rules (doc 39 §7-2b/2c).
//
// Lives OUTSIDE the panel component so (a) the workspace owns it and a refetch — or a failed
// refetch — can never wipe a half-written disapproval (deep review C6), (b) finding cards can
// drive the scope selection, and (c) the validation is unit-tested. `validateDraft` mirrors
// runtime/app/review/verdicts.py::validate_disapproval rule for rule; the server stays the
// authority (its 422 list is still rendered), this just stops an invalid verdict being sent.

import type { DisapprovalCause, DisapprovalType, ReviewVerdictBody } from './api-client';

export type VerdictMode = 'approve' | 'disapprove' | 'cant_verify';
export type VerdictScope = 'whole_case' | 'findings';

export interface VerdictDraft {
  mode: VerdictMode;
  note: string;
  type: DisapprovalType | null;
  scope: VerdictScope | null;
  targets: string[];
  cause: DisapprovalCause | null;
  concluded: string;
  shouldHave: string;
  inputOrRule: string;
}

export const EMPTY_DRAFT: VerdictDraft = {
  mode: 'approve',
  note: '',
  type: null,
  scope: null,
  targets: [],
  cause: null,
  concluded: '',
  shouldHave: '',
  inputOrRule: '',
};

// What the reviewer can pick. `partial` is NOT offered: it duplicated `partially_correct`
// (two labels for one judgment). The enum value stays valid server-side and in the DB for
// legacy rows — see verdictLabel.
export const DISAPPROVAL_TYPES: { value: DisapprovalType; label: string }[] = [
  { value: 'missed_finding', label: 'Missed a finding' },
  { value: 'hallucinated', label: 'Hallucinated a claim' },
  { value: 'wrong', label: 'Wrong conclusion' },
  { value: 'partially_correct', label: 'Partially correct' },
];

export const CAUSES: { value: DisapprovalCause; label: string; hint: string }[] = [
  { value: 'content_gap', label: 'Content gap', hint: 'a rule or source the corpus does not have yet' },
  { value: 'reasoning_error', label: 'Reasoning error', hint: 'the inputs were there; the conclusion was wrong' },
  { value: 'bad_input', label: 'Bad input', hint: 'extraction or intake fed the audit something wrong' },
  { value: 'stale_data_source', label: 'Stale data source', hint: 'a source Tyndale relies on is out of date' },
];

export type DraftField = 'type' | 'scope' | 'targets' | 'cause' | 'concluded' | 'shouldHave' | 'inputOrRule';

export interface DraftValidation {
  valid: boolean;
  problems: Partial<Record<DraftField, string>>;
}

/** Approve / Can't verify are always sendable (the note is optional). A disapproval needs a
 *  type, a scope (whole case, or ≥1 finding that is actually on this case), exactly one cause,
 *  and all three prompts non-blank. */
export function validateDraft(d: VerdictDraft, caseFindingIds: readonly string[]): DraftValidation {
  if (d.mode !== 'disapprove') return { valid: true, problems: {} };
  const problems: DraftValidation['problems'] = {};
  if (!d.type || !DISAPPROVAL_TYPES.some((t) => t.value === d.type)) problems.type = 'Choose what kind of miss this was.';
  if (!d.scope) {
    problems.scope = 'Choose the whole case, or select the finding(s) it applies to.';
  } else if (d.scope === 'findings') {
    const onCase = d.targets.filter((t) => caseFindingIds.includes(t));
    if (!d.targets.length) problems.targets = 'Select at least one finding (on its card, or here).';
    else if (onCase.length !== d.targets.length) problems.targets = 'A selected finding is no longer on this case.';
  }
  if (!d.cause) problems.cause = 'Pick exactly one cause — it decides where the fix goes.';
  if (!d.concluded.trim()) problems.concluded = 'Say what Tyndale concluded.';
  if (!d.shouldHave.trim()) problems.shouldHave = 'Say what it should have concluded.';
  if (!d.inputOrRule.trim()) problems.inputOrRule = 'Name the input or rule that was the problem.';
  return { valid: Object.keys(problems).length === 0, problems };
}

/** The request body for a VALID draft (trimmed; disapproval-only fields left out otherwise). */
export function toVerdictBody(d: VerdictDraft): ReviewVerdictBody {
  const body: ReviewVerdictBody = { action: d.mode, note: d.note.trim() || undefined };
  if (d.mode !== 'disapprove') return body;
  return {
    ...body,
    verdict_type: d.type ?? undefined,
    scope: d.scope ?? undefined,
    target_findings: d.scope === 'findings' ? [...d.targets] : undefined,
    cause: d.cause ?? undefined,
    structured_note: {
      concluded: d.concluded.trim(),
      should_have_concluded: d.shouldHave.trim(),
      input_or_rule: d.inputOrRule.trim(),
    },
  };
}

/** Anything the reviewer would lose if the draft vanished. */
export function isDirty(d: VerdictDraft): boolean {
  return (
    d.mode !== EMPTY_DRAFT.mode || !!d.note.trim() || !!d.type || !!d.scope || d.targets.length > 0 ||
    !!d.cause || !!d.concluded.trim() || !!d.shouldHave.trim() || !!d.inputOrRule.trim()
  );
}

/** Toggle one finding in the scope selection (from a finding card or the panel list).
 *  Selecting a finding IS choosing scope=findings; clearing the last one leaves scope alone. */
export function toggleTarget(d: VerdictDraft, findingId: string): VerdictDraft {
  const has = d.targets.includes(findingId);
  const targets = has ? d.targets.filter((t) => t !== findingId) : [...d.targets, findingId];
  return { ...d, targets, scope: has ? d.scope : 'findings' };
}

const VERDICT_LABELS: Record<string, string> = {
  correct: 'Approved',
  unable_to_verify: "Can't verify",
  missed_finding: 'Missed a finding',
  hallucinated: 'Hallucinated a claim',
  wrong: 'Wrong conclusion',
  partially_correct: 'Partially correct',
  // No longer offered (it duplicated partially_correct) — older rows still carry it.
  partial: 'Partially correct (legacy)',
};

export function verdictLabel(verdict: string): string {
  return VERDICT_LABELS[verdict] ?? verdict.replace(/_/g, ' ');
}
