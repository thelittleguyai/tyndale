/**
 * e2e round 3 R4 — the guided confirmations cards say the code and ONE plain sentence; the rest
 * waits under "Show me what this usually looks like". The split is the chat-first card's own
 * (splitTranslation), held to the same cases as the server's twin (fact_copy.split_translation).
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { IntakeScreen } from '@tyndale/shared';

import { IntakeBody, type IntakeBodyProps } from '../components/intake/IntakeBody';
import { splitTranslation } from '../lib/line-item-copy';

const shared = require('../../../runtime/tests/fixtures/line_item_copy_cases.json') as {
  cases: { input: string; headline: string; rest: string | null }[];
};

describe('one split, two runtimes', () => {
  it.each(shared.cases.map((c) => [c.input.slice(0, 30) || 'empty', c] as const))('%s', (_n, c) => {
    expect(splitTranslation(c.input)).toEqual({ headline: c.headline, rest: c.rest });
  });
});

const noop = () => undefined;
const props = (screen: IntakeScreen): IntakeBodyProps => ({
  screen, busy: false, act: noop, onCapture: noop, onEdit: noop, onAttest: noop,
  onAttestDecline: noop, onPlanConfirm: noop, onRun: noop, onExit: noop, onHandoff: noop,
});

describe('a guided confirmations card', () => {
  it('shows the code and one sentence, and keeps the long text under the disclosure', () => {
    const screen: IntakeScreen = {
      id: 'confirmations', kind: 'confirmations', progress_group: 'confirmations', skippable: false,
      copy: { yes: 'Yes', no: 'No', not_sure: "I'm not sure", primary: 'Done', more: 'Show me what this usually looks like' },
      data: { line_items: [
        { line_item_id: 'a', code: '99214', text: 'A charge on your bill.', more: 'An office or outpatient visit for an established patient, coded at the second-highest of four standard visit levels.' },
        { line_item_id: 'b', code: '36415', text: 'Blood drawn from your arm.', more: null },
      ] },
    };
    const r = render(<IntakeBody {...props(screen)} />);
    expect(r.getByTestId('intake-fact-a-text').props.children).toBe('99214 · A charge on your bill.');
    expect(r.getByTestId('intake-fact-b-text').props.children).toBe('36415 · Blood drawn from your arm.');
    expect(r.queryByText(/second-highest/)).toBeNull(); // folded until asked for
    expect(r.getAllByText('Show me what this usually looks like')).toHaveLength(1); // only where there is more
    fireEvent.press(r.getByText('Show me what this usually looks like'));
    expect(r.getByText(/second-highest of four standard visit levels/)).toBeTruthy();
  });
});
