import { render } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

import { ThreeNumberMoment } from '../components/thread/MomentCards';
import { StatusCard } from '../components/thread/StatusCard';
import { ThreadEntry } from '../components/thread/ThreadEntry';

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
});
