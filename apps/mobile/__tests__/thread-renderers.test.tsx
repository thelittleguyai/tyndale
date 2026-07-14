import { render } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

import { fireEvent } from '@testing-library/react-native';

import { ThreeNumberMoment } from '../components/thread/MomentCards';
import { StatusCard } from '../components/thread/StatusCard';
import { ThreadEntry } from '../components/thread/ThreadEntry';
import { ThreadSuggestion } from '../components/thread/ThreadSuggestion';

describe('chat-first thread renderers (DL-91)', () => {
  it('StatusCard renders the four labeled flow-stage bars', () => {
    const { getByText } = render(
      <StatusCard
        payload={{
          stages: [
            { key: 'extraction', label: 'Reading your documents', state: 'done' },
            { key: 'translate', label: 'Sorting the charges', state: 'done' },
            { key: 'encounter', label: 'Confirming what happened', state: 'active' },
            { key: 'audit', label: 'Checking every charge', state: 'pending' },
          ],
          terminal: false,
        }}
      />,
    );
    expect(getByText('Reading your documents')).toBeTruthy();
    expect(getByText('Checking every charge')).toBeTruthy();
  });

  it('ThreeNumberMoment shows all three numbers + the reveal headline (D0)', () => {
    const { getByText } = render(
      <ThreeNumberMoment
        payload={{
          variant: 'three_number',
          provider_billed: 1200,
          eob_member_responsibility: 800,
          tyndale_computed: 300,
          delta: 500,
          headline: 'You may not owe $500.00',
        }}
      />,
    );
    expect(getByText('You may not owe $500.00')).toBeTruthy();
    expect(getByText('$1,200.00')).toBeTruthy();
    expect(getByText('$300.00')).toBeTruthy();
  });

  it('ThreadEntry dispatches by kind', () => {
    const msg = {
      message_id: 'm',
      conversation_id: 'c',
      sequence_number: 1,
      role: 'system',
      kind: 'status_card_update',
      content: null,
      status: 'complete',
      created_at: '',
      payload: {
        stages: [{ key: 'audit', label: 'Checking charges', state: 'active' }],
        terminal: false,
      },
    } as unknown as Message;
    const { getByText } = render(
      <ThreadEntry
        message={msg}
        caseFileId="cf"
        conversationId="c"
        drafts={{}}
        onRespond={() => undefined}
        onNote={() => undefined}
      />,
    );
    expect(getByText('Checking charges')).toBeTruthy();
  });

  it('ThreadSuggestion shows the confirm prompt + a working Confirm tap when active (D4b)', () => {
    const onConfirm = jest.fn();
    const { getByText, queryByText, rerender } = render(
      <ThreadSuggestion
        payload={{ text: "I've marked the second charge as 'didn't happen'", summary: 's', mappings: [] }}
        active
        onConfirm={onConfirm}
      />,
    );
    expect(getByText("I've marked the second charge as 'didn't happen'")).toBeTruthy();
    fireEvent.press(getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalled();
    // once confirmed/superseded (inactive) the button is gone
    rerender(
      <ThreadSuggestion
        payload={{ text: 'done', summary: 's', mappings: [] }}
        active={false}
        onConfirm={onConfirm}
      />,
    );
    expect(queryByText('Confirm')).toBeNull();
  });
});
