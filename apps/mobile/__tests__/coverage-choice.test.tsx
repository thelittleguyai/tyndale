/**
 * e2e round 3 R3 — "Which of these did you mean?" arrives WITH its choices. "my deductible is
 * $2,000"-style words that fit two checklist items (the plan's deductible, or what has been paid
 * toward it) used to post the line alone: nothing to tap. The chips name the items; a pick
 * pre-selects that item with the typed value — the confirming tap on the checklist still saves.
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

import { ThreadEntry } from '../components/thread/ThreadEntry';

const line = (payload: Record<string, unknown>) =>
  ({
    message_id: 'm', conversation_id: 'c', sequence_number: 3, role: 'system', kind: 'system_message',
    content: 'I want to mark the right one. Which of these did you mean?', status: 'complete', created_at: '',
    payload,
  }) as unknown as Message;

const choice = {
  text: 'I want to mark the right one. Which of these did you mean?',
  tone: 'neutral',
  coverage_choice: {
    value: 2000,
    options: [
      { field: 'deductible_amount', label: 'Your deductible' },
      { field: 'deductible_met', label: 'What you had paid toward it' },
    ],
  },
};

describe('the which-did-you-mean line', () => {
  it('renders its choices as chips, and a pick pre-selects that item with the typed value', () => {
    const onCoverageChoice = jest.fn();
    const { getByText, getByTestId } = render(
      <ThreadEntry message={line(choice)} caseFileId="cf" conversationId="c" drafts={{}}
        onRespond={() => undefined} onNote={() => undefined} onCoverageChoice={onCoverageChoice} />,
    );
    expect(getByText(choice.text)).toBeTruthy();
    expect(getByTestId('suggested-replies')).toBeTruthy();
    fireEvent.press(getByText('What you had paid toward it'));
    expect(onCoverageChoice).toHaveBeenCalledWith('deductible_met', 2000);
  });

  it('a plain system line still renders without chips', () => {
    const { queryByTestId, getByText } = render(
      <ThreadEntry message={line({ text: 'Saved.', tone: 'neutral' })} caseFileId="cf" conversationId="c"
        drafts={{}} onRespond={() => undefined} onNote={() => undefined} />,
    );
    expect(getByText('Saved.')).toBeTruthy();
    expect(queryByTestId('suggested-replies')).toBeNull();
  });
});
