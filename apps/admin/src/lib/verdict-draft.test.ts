import { describe, expect, it } from 'vitest';

import {
  DISAPPROVAL_TYPES,
  EMPTY_DRAFT,
  isDirty,
  toVerdictBody,
  toggleTarget,
  validateDraft,
  verdictLabel,
  type VerdictDraft,
} from './verdict-draft';

const FINDINGS = ['f-1', 'f-2'];
const FULL: VerdictDraft = {
  ...EMPTY_DRAFT,
  mode: 'disapprove',
  type: 'missed_finding',
  scope: 'whole_case',
  cause: 'content_gap',
  concluded: 'no finding on the bundled line',
  shouldHave: 'an NCCI bundling finding',
  inputOrRule: 'ncci edit table',
};

describe('validateDraft mirrors the server (§7-2b)', () => {
  it('approve and cant_verify are always sendable, note or not', () => {
    expect(validateDraft(EMPTY_DRAFT, FINDINGS).valid).toBe(true);
    expect(validateDraft({ ...EMPTY_DRAFT, mode: 'cant_verify' }, []).valid).toBe(true);
  });

  it('a bare disapproval is blocked, naming EVERY missing field at once', () => {
    const v = validateDraft({ ...EMPTY_DRAFT, mode: 'disapprove' }, FINDINGS);
    expect(v.valid).toBe(false);
    expect(Object.keys(v.problems).sort()).toEqual(
      ['cause', 'concluded', 'inputOrRule', 'scope', 'shouldHave', 'type'].sort(),
    );
  });

  it('a complete disapproval passes', () => {
    expect(validateDraft(FULL, FINDINGS)).toEqual({ valid: true, problems: {} });
  });

  it('scope=findings needs at least one finding, and only ones on this case', () => {
    expect(validateDraft({ ...FULL, scope: 'findings' }, FINDINGS).problems.targets).toMatch(/at least one/);
    expect(validateDraft({ ...FULL, scope: 'findings', targets: ['f-1'] }, FINDINGS).valid).toBe(true);
    expect(validateDraft({ ...FULL, scope: 'findings', targets: ['gone'] }, FINDINGS).problems.targets).toMatch(
      /no longer on this case/,
    );
  });

  it('whitespace is not a note, and one cause is required', () => {
    expect(validateDraft({ ...FULL, inputOrRule: '   ' }, FINDINGS).problems.inputOrRule).toBeTruthy();
    expect(validateDraft({ ...FULL, concluded: '\n' }, FINDINGS).problems.concluded).toBeTruthy();
    expect(validateDraft({ ...FULL, cause: null }, FINDINGS).problems.cause).toBeTruthy();
    expect(validateDraft({ ...FULL, type: null }, FINDINGS).problems.type).toBeTruthy();
  });
});

describe('the duplicate choice is gone from the UI, not from history', () => {
  it('offers partially_correct and never partial', () => {
    const offered = DISAPPROVAL_TYPES.map((t) => t.value);
    expect(offered).toContain('partially_correct');
    expect(offered).not.toContain('partial');
    expect(offered).not.toContain('correct'); // that is the Approve action
    expect(offered).not.toContain('unable_to_verify'); // that is Can't verify
  });

  it('renders a legacy partial row as such', () => {
    expect(verdictLabel('partial')).toBe('Partially correct (legacy)');
    expect(verdictLabel('partially_correct')).toBe('Partially correct');
    expect(verdictLabel('correct')).toBe('Approved');
    expect(verdictLabel('some_future_value')).toBe('some future value');
  });
});

describe('toVerdictBody', () => {
  it('sends only what the action needs, trimmed', () => {
    expect(toVerdictBody({ ...EMPTY_DRAFT, note: '  ok  ' })).toEqual({ action: 'approve', note: 'ok' });
    expect(toVerdictBody({ ...EMPTY_DRAFT, mode: 'cant_verify' })).toEqual({ action: 'cant_verify', note: undefined });
    const body = toVerdictBody({ ...FULL, scope: 'findings', targets: ['f-2'], concluded: '  x ' });
    expect(body.scope).toBe('findings');
    expect(body.target_findings).toEqual(['f-2']);
    expect(body.structured_note?.concluded).toBe('x');
    expect(toVerdictBody(FULL).target_findings).toBeUndefined(); // whole case carries no targets
  });
});

describe('draft safety + scope selection', () => {
  it('knows when there is something to lose', () => {
    expect(isDirty(EMPTY_DRAFT)).toBe(false);
    expect(isDirty({ ...EMPTY_DRAFT, note: ' ' })).toBe(false);
    expect(isDirty({ ...EMPTY_DRAFT, concluded: 'x' })).toBe(true);
    expect(isDirty({ ...EMPTY_DRAFT, mode: 'disapprove' })).toBe(true);
  });

  it('selecting a finding on its card chooses scope=findings; deselecting keeps the scope', () => {
    const one = toggleTarget(EMPTY_DRAFT, 'f-1');
    expect(one).toMatchObject({ scope: 'findings', targets: ['f-1'] });
    const two = toggleTarget(one, 'f-2');
    expect(two.targets).toEqual(['f-1', 'f-2']);
    const back = toggleTarget(toggleTarget(two, 'f-1'), 'f-2');
    expect(back).toMatchObject({ scope: 'findings', targets: [] });
    expect(EMPTY_DRAFT.targets).toEqual([]); // never mutated
  });
});
