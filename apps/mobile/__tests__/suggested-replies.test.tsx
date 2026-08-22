/** Item 3 (Brock 2026-08-22): tap-to-reply chips under the newest assistant turn. */

import { fireEvent, render, waitFor } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

const mockGetConversation = jest.fn();
const mockStreamMessage = jest.fn();
jest.mock('../lib/api-client', () => ({
  getConversation: (...a: unknown[]) => mockGetConversation(...a),
  streamMessage: (...a: unknown[]) => mockStreamMessage(...a),
  stopStream: jest.fn(),
}));

import { SuggestedReplies } from '../components/chat/SuggestedReplies';
import { ChatThread } from '../components/chat/ChatThread';

function assistant(over: Partial<Message> = {}): Message {
  return {
    message_id: 'a1',
    conversation_id: 'c1',
    sequence_number: 2,
    role: 'assistant',
    content: 'Do you have a bill in hand?',
    content_chunks: [{ tier: 'A', text: 'Do you have a bill in hand?', citations: [] }],
    status: 'complete',
    created_at: new Date().toISOString(),
    ...over,
  };
}

describe('SuggestedReplies', () => {
  it('renders up to four chips and tapping sends the literal text', () => {
    const onPick = jest.fn();
    const { getByText, queryByText } = render(
      <SuggestedReplies replies={['Yes', 'No', 'Maybe', 'Later', 'Fifth']} onPick={onPick} />,
    );
    fireEvent.press(getByText('Yes'));
    expect(onPick).toHaveBeenCalledWith('Yes');
    expect(queryByText('Fifth')).toBeNull();
  });
});

describe('ChatThread chips', () => {
  beforeEach(() => {
    mockGetConversation.mockReset();
    mockStreamMessage.mockReset();
    mockStreamMessage.mockImplementation(async (_id: string, _c: string, onEvent: (e: unknown) => void) => {
      onEvent({ event: 'done', data: {} });
    });
  });

  it('shows chips under the newest complete assistant turn; a tap sends that text', async () => {
    const user = (id: string, content: string) => ({
      message_id: id, conversation_id: 'c1', sequence_number: 1, role: 'user' as const,
      content, status: 'complete' as const, created_at: new Date().toISOString(),
    });
    const withChips = {
      messages: [user('u1', 'hi'), assistant({ suggested_replies: ['Yes, I have a bill', 'No bill yet'] })],
    };
    // After the tap the hook reloads from the server, which now ends with the user's reply
    // (the real server appends the new turns) — the old chips hang off an older turn.
    const afterReply = { messages: [...withChips.messages, user('u2', 'Yes, I have a bill')] };
    mockGetConversation.mockResolvedValueOnce(withChips).mockResolvedValue(afterReply);
    const { findByText, queryByText } = render(<ChatThread conversationId="c1" />);
    const chip = await findByText('Yes, I have a bill');
    fireEvent.press(chip);
    await waitFor(() => expect(mockStreamMessage).toHaveBeenCalled());
    expect(mockStreamMessage.mock.calls[0][1]).toBe('Yes, I have a bill');
    // The tap became the user's message; the chips are gone once they replied.
    await waitFor(() => expect(queryByText('No bill yet')).toBeNull());
  });

  it('renders no chips when the newest turn has none', async () => {
    mockGetConversation.mockResolvedValue({ messages: [assistant({ suggested_replies: null })] });
    const { findByText, queryByTestId } = render(<ChatThread conversationId="c1" />);
    await findByText('Do you have a bill in hand?');
    expect(queryByTestId('suggested-replies')).toBeNull();
  });
});
