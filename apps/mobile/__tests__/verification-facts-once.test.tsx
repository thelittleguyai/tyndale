/**
 * e2e round 3 R1 — an answered encounter fact is never asked again. The server refreshes every
 * verification card with `answered` (the answer on file, wherever it was given) and `awaiting`
 * (what is still owed). A reopened thread used to show answered facts as unanswered — with the
 * nudge — and route free text on a finished audit to the verification mapper.
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { VerificationRequestPayload } from '@tyndale/shared';

import { ThreadVerification, owedItems } from '../components/thread/ThreadVerification';

jest.mock('expo-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => children,
  Stack: { Screen: () => null },
  useRouter: () => ({ push: jest.fn() }),
}));

const item = (id: string, words: string) => ({
  line_item_id: id, code: '99214', code_system: 'CPT', raw_description: 'x',
  plain_language_translation: words, plain_language_context: '', example_scenarios: [],
  high_risk: false, billed_amount: 100, units: 1,
});
const base: VerificationRequestPayload = {
  intro: 'Confirm these', nudge: 'Tap one of the buttons on a card above to answer', group_index: 0,
  line_items: [item('a', 'A visit with a doctor you have seen before.'), item('b', 'Blood drawn.'),
    item('c', 'A copy a second read appended.')],
};

describe('a refreshed verification card', () => {
  it('shows answers on file, locked, owes nothing, and hides a row that is no longer a fact', () => {
    const payload: VerificationRequestPayload = { ...base, answered: { a: 'yes', b: 'not_sure' }, awaiting: [] };
    const onRespond = jest.fn();
    const r = render(<ThreadVerification payload={payload} drafts={{}} onRespond={onRespond} onNote={jest.fn()} />);
    expect(r.queryByTestId('verification-nudge')).toBeNull(); // nothing is owed
    expect(r.queryByText(/A copy a second read appended/)).toBeNull(); // not one of the case's facts
    expect(r.getAllByText('✓')).toHaveLength(2); // both answers render as chosen
    fireEvent.press(r.getAllByText("That didn't happen")[0]);
    expect(onRespond).not.toHaveBeenCalled(); // an answer on file is shown, never re-asked
    expect(owedItems(payload)).toEqual([]);
  });

  it('asks only the fact still owed, and the nudge asks for that one', () => {
    const payload: VerificationRequestPayload = { ...base, answered: { a: 'yes' }, awaiting: ['b'] };
    const onRespond = jest.fn();
    const r = render(<ThreadVerification payload={payload} drafts={{}} onRespond={onRespond} onNote={jest.fn()} />);
    expect(r.getByTestId('verification-nudge')).toBeTruthy();
    expect(owedItems(payload).map((i) => i.line_item_id)).toEqual(['b']);
    fireEvent.press(r.getAllByText("Yes, that's right")[1]);
    expect(onRespond).toHaveBeenCalledWith('b', 'yes');
  });

  it('renders nothing when none of its rows is a fact any more', () => {
    const payload: VerificationRequestPayload = { ...base, answered: {}, awaiting: [] };
    const r = render(<ThreadVerification payload={payload} drafts={{}} onRespond={jest.fn()} onNote={jest.fn()} />);
    expect(r.toJSON()).toBeNull();
  });

  it('a card no server has refreshed keeps the session-drafts behaviour', () => {
    expect(owedItems(base).map((i) => i.line_item_id)).toEqual(['a', 'b', 'c']);
    const r = render(<ThreadVerification payload={base} drafts={{}} onRespond={jest.fn()} onNote={jest.fn()} />);
    expect(r.getByTestId('verification-nudge')).toBeTruthy();
  });
});
