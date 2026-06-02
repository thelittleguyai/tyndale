import { fireEvent, render } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

import { ChatMessage } from '../../components/chat/ChatMessage';

const base = (over: Partial<Message>): Message => ({
  message_id: 'm1',
  conversation_id: 'c1',
  sequence_number: 1,
  role: 'assistant',
  content: null,
  status: 'complete',
  created_at: '2026-01-01T00:00:00Z',
  ...over,
});

describe('ChatMessage variants', () => {
  it('renders a user message', () => {
    const { getByText } = render(
      <ChatMessage
        message={base({ role: 'user', content: 'Hello there', status: 'complete' })}
        conversationId="c1"
        onCitation={() => undefined}
      />,
    );
    expect(getByText('Hello there')).toBeTruthy();
  });

  it('renders tiered A/B/C chunks + a citation chip + confidence', () => {
    const msg = base({
      content_chunks: [
        { tier: 'A', text: 'The facts here', citations: [] },
        { tier: 'B', text: 'A legal claim', citations: [{ title: 'NSA overview', source_id: 's1' }] },
        { tier: 'C', text: 'Do this next', citations: [] },
      ],
      confidence_overall: 0.8,
    });
    const { getByText } = render(
      <ChatMessage message={msg} conversationId="c1" onCitation={() => undefined} />,
    );
    expect(getByText('The facts here')).toBeTruthy();
    expect(getByText('A legal claim')).toBeTruthy();
    expect(getByText('Do this next')).toBeTruthy();
    expect(getByText('NSA overview')).toBeTruthy();
    expect(getByText('80% confident')).toBeTruthy();
  });

  it('renders a failed message with a working retry', () => {
    const onRetry = jest.fn();
    const { getByText } = render(
      <ChatMessage
        message={base({ status: 'failed', error_message: 'It broke' })}
        conversationId="c1"
        onCitation={() => undefined}
        onRetry={onRetry}
      />,
    );
    expect(getByText('It broke')).toBeTruthy();
    fireEvent.press(getByText('Retry'));
    expect(onRetry).toHaveBeenCalled();
  });

  it('renders a stopped message note', () => {
    const { getByText } = render(
      <ChatMessage
        message={base({ status: 'stopped', content: 'partial answer' })}
        conversationId="c1"
        onCitation={() => undefined}
      />,
    );
    expect(getByText('Generation stopped.')).toBeTruthy();
  });
});
