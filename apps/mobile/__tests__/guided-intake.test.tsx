/**
 * The guided intake UI (doc 40): it draws what the server's planner hands it — no sequence and
 * no product copy of its own. These pin the rules the packet states about what is SHOWN.
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { IntakeProgress, IntakeScreen } from '@tyndale/shared';

import { IntakeBody, type IntakeBodyProps } from '../components/intake/IntakeBody';
import { IntakeProgressBar } from '../components/intake/IntakeProgressBar';

const noop = () => undefined;
const props = (screen: IntakeScreen, over: Partial<IntakeBodyProps> = {}): IntakeBodyProps => ({
  screen, busy: false, act: noop, onCapture: noop, onEdit: noop, onAttest: noop,
  onAttestDecline: noop, onPlanConfirm: noop, onRun: noop, onExit: noop, onHandoff: noop, ...over,
});
const screen = (s: Partial<IntakeScreen>): IntakeScreen => ({
  id: 'x', kind: 'info', progress_group: null, copy: {}, data: {}, skippable: false, ...s,
});

const GROUPS = ['bill', 'card', 'plan_rules', 'eob', 'timeline', 'about_you', 'confirmations'] as const;
const progress = (filled: string[], over: Partial<IntakeProgress> = {}): IntakeProgress => ({
  segments: GROUPS.map((g) => ({ group: g, filled: filled.includes(g), label: g })),
  filled: filled.length, total: 7, line: null, note: null, glosses: {}, high_water: filled, ...over,
});

describe('progress bar (§A8)', () => {
  it('shows seven segments and NO counter before anything lands — never "Step N of M"', () => {
    const { queryByTestId, getAllByLabelText, toJSON } = render(<IntakeProgressBar progress={progress([])} />);
    expect(queryByTestId('intake-progress-line')).toBeNull();
    expect(GROUPS.every((g) => getAllByLabelText(g).length === 1)).toBe(true);
    expect(JSON.stringify(toJSON())).not.toMatch(/Step \d+ of/);
  });

  it('frames the first landing as a start, and explains a segment a reclassified paper no longer backs', () => {
    const { getByTestId } = render(
      <IntakeProgressBar progress={progress(['bill'], { line: '1 of 7 — nice start', note: 'I moved one of your papers to a new group. Your progress stays the same.' })} />,
    );
    expect(getByTestId('intake-progress-line').props.children).toBe('1 of 7 — nice start');
    expect(getByTestId('intake-segment-bill').props.className).toContain('bg-accent'); // still filled
    expect(getByTestId('intake-progress-note').props.children).toMatch(/progress stays/);
  });
});

describe('capture screens', () => {
  const eob = screen({
    id: 'eob', kind: 'capture', skippable: true, data: { expect: 'eob', have: 0, note: null },
    copy: { body: 'It shows what your insurer paid.', gloss_eob: 'An EOB is the statement your insurer sends after a visit.', primary: 'Add my EOB', skip: "I don't have it", skip_consequence: "I can't check your insurer's math.", trust: 'Encrypted. Never sold. Used only for your audit.' },
  });

  it('glosses the term, shows trust microcopy at the capture, and a skip says what it costs', () => {
    const onCapture = jest.fn();
    const act = jest.fn();
    const { getByTestId, getByText } = render(<IntakeBody {...props(eob, { onCapture, act })} />);
    expect(getByTestId('intake-glosses')).toBeTruthy();
    expect(getByText('Encrypted. Never sold. Used only for your audit.')).toBeTruthy();
    expect(getByText("I can't check your insurer's math.")).toBeTruthy();
    fireEvent.press(getByTestId('intake-capture'));
    expect(onCapture).toHaveBeenCalledWith('eob'); // the EXISTING capture flow, with the expectation
    fireEvent.press(getByTestId('intake-skip'));
    expect(act).toHaveBeenCalledWith('skip');
  });

  it('says a wrong document plainly and still offers the way on — no dead end (§C12)', () => {
    const wrong = screen({ ...eob, id: 'bill', copy: { ...eob.copy, skip: undefined as unknown as string, no_bill: "I don't have the bill" }, data: { expect: 'itemized_bill', note: 'That looks like an insurance card, not a bill or EOB.' } });
    const { getByTestId, getByText } = render(<IntakeBody {...props(wrong)} />);
    expect(getByTestId('intake-note')).toBeTruthy();
    expect(getByText("I don't have the bill")).toBeTruthy();
  });
});

describe('a way out always says what it costs', () => {
  it('a typed-answer screen shows the skip WITH its consequence', () => {
    const act = jest.fn();
    const s = screen({
      id: 'insurer', kind: 'fields', skippable: true,
      copy: { body: 'I could not find it on your papers.', field_payer: 'Insurer name', primary: 'Save', skip: 'Skip for now', skip_consequence: "Without it, I can't look up your plan. I may need to ask you more." },
      data: { fields: [{ name: 'payer_name', slot: 'field_payer', value: null, input: 'text' }] },
    });
    const { getByTestId, getByText } = render(<IntakeBody {...props(s, { act })} />);
    expect(getByText("Without it, I can't look up your plan. I may need to ask you more.")).toBeTruthy();
    fireEvent.press(getByTestId('intake-skip'));
    expect(act).toHaveBeenCalledWith('skip');
  });

  it('a choice with "I\'m not sure" says what not knowing costs', () => {
    const act = jest.fn();
    const s = screen({
      id: 'plan_year', kind: 'choice', skippable: true,
      copy: { body: 'Many plans start in January, but not all.', opt_not_sure: "I'm not sure", not_sure_consequence: "That's fine. I just won't know if a month is missing." },
      data: { options: [{ value: '7', label: 'July' }, { value: 'not_sure', slot: 'opt_not_sure' }] },
    });
    const { getByTestId, getByText } = render(<IntakeBody {...props(s, { act })} />);
    expect(getByText("That's fine. I just won't know if a month is missing.")).toBeTruthy();
    fireEvent.press(getByTestId('intake-option-not_sure'));
    expect(act).toHaveBeenCalledWith('continue', { choice: 'not_sure' });
  });
});

describe('confirmations are generated, not fixed (§A4-5)', () => {
  it.each([1, 5])('renders exactly the %i fact(s) the engine emitted and needs an answer to each', (n) => {
    const act = jest.fn();
    const items = Array.from({ length: n }, (_, i) => ({ line_item_id: `li-${i}`, text: `Fact ${i}`, context: null }));
    const s = screen({ id: 'confirmations', kind: 'confirmations', copy: { yes: 'Yes', no: 'No', not_sure: "I'm not sure", primary: 'Done', not_sure_note: "That's fine." }, data: { line_items: items } });
    const { getByTestId, getAllByText } = render(<IntakeBody {...props(s, { act })} />);
    expect(getAllByText(/^Fact \d$/)).toHaveLength(n);
    fireEvent.press(getByTestId('intake-facts-done'));
    expect(act).not.toHaveBeenCalled(); // not until every fact is answered
    items.forEach((it) => fireEvent.press(getByTestId(`intake-fact-${it.line_item_id}-yes`)));
    fireEvent.press(getByTestId('intake-facts-done'));
    expect(act).toHaveBeenCalledWith('continue', { confirmations: items.map((it) => ({ line_item_id: it.line_item_id, response: 'yes' })) });
  });
});

describe('timeline (§A7)', () => {
  it('names the gaps with their honest consequence and asks the completeness question as a card', () => {
    const act = jest.fn();
    const s = screen({
      id: 'timeline', kind: 'timeline',
      copy: { gap_lines: "I don't see one for February.", gap_consequence: "Without it, I'll show your share as a range.", confirm_text: 'I count 2 EOBs, January to June, none for anyone else on your plan. Is that all of them?', confirm_yes: "Yes, that's all", confirm_no: 'No, there are more', add_more: 'Add another EOB', visit_marker: 'Your visit', after_visit: 'After your visit. It does not change this bill.' },
      data: { months: [{ label: 'Jan 2026', has_eob: true, is_visit_month: false }, { label: 'Feb 2026', has_eob: false, is_visit_month: false }], rows: [{ document_id: 'd9', date: '2026-08-20', month_label: 'Aug 2026', after_visit: true, network: null }] },
    });
    const { getByTestId, getByText } = render(<IntakeBody {...props(s, { act })} />);
    expect(getByTestId('intake-timeline-gaps')).toBeTruthy();
    expect(getByText("Without it, I'll show your share as a range.")).toBeTruthy();
    expect(getByText(/Aug 2026 — After your visit/)).toBeTruthy(); // shown, and visibly not counted
    expect(getByTestId('intake-completeness').props.children).toMatch(/Is that all of them\?/);
    fireEvent.press(getByTestId('intake-complete-yes'));
    expect(act).toHaveBeenCalledWith('yes');
  });
});

describe('readiness (#17)', () => {
  it('gives every editable line an edit link and says what an unresolved one limits', () => {
    const onEdit = jest.fn();
    const s = screen({
      id: 'readiness', kind: 'readiness',
      copy: { resolved: 'Have it', unresolved: 'Missing', skipped: 'Skipped', edit: 'Change', primary: 'Check my bill' },
      data: { can_run: true, lines: [
        { key: 'bill', label: 'Your bill', resolved: true, state: 'resolved', limits: null, edit_screen: null },
        { key: 'eob', label: "Your insurer's statement", resolved: false, state: 'skipped', limits: "No insurer statement. I can't check your insurer's math.", edit_screen: 'eob' },
      ] },
    });
    const { getByTestId, getByText, queryByTestId } = render(<IntakeBody {...props(s, { onEdit })} />);
    expect(getByText("No insurer statement. I can't check your insurer's math.")).toBeTruthy();
    expect(queryByTestId('intake-edit-bill')).toBeNull(); // nothing to edit → no link
    fireEvent.press(getByTestId('intake-edit-eob'));
    expect(onEdit).toHaveBeenCalledWith('eob');
  });
});

describe('attest-and-proceed, hosted (§B13)', () => {
  it('offers the seven relationships, a confirm, and ALWAYS the decline path', () => {
    const onAttest = jest.fn();
    const onAttestDecline = jest.fn();
    const rel = ['spouse_partner', 'parent_guardian', 'adult_child_caregiver', 'healthcare_poa', 'court_guardian', 'executor', 'other'];
    const s = screen({ id: 'attest', kind: 'attest', copy: { primary: 'I confirm', decline: "I can't confirm this" }, data: { declined: false, intro: 'This bill is for someone else.', confirm: 'I am allowed to act for them.', relationships: rel.map((r) => ({ value: r, label: r })) } });
    const { getByTestId } = render(<IntakeBody {...props(s, { onAttest, onAttestDecline })} />);
    fireEvent.press(getByTestId('intake-attest-confirm'));
    expect(onAttest).not.toHaveBeenCalled(); // a relationship must be on the record first
    fireEvent.press(getByTestId('intake-attest-spouse_partner'));
    fireEvent.press(getByTestId('intake-attest-confirm'));
    expect(onAttest).toHaveBeenCalledWith('spouse_partner');
    fireEvent.press(getByTestId('intake-attest-decline'));
    expect(onAttestDecline).toHaveBeenCalled();
  });
});
