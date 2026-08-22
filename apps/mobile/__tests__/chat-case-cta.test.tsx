/** 2026-08-22 case-intent fix: the create-case button renders from the LIVE-path shape
 *  (an action in the turn's citations), and "upload a bill" is one tap away everywhere. */

import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockPush = jest.fn();
jest.mock('expo-router', () => {
  const React = require('react');
  return {
    useRouter: () => ({ push: mockPush, replace: jest.fn(), back: jest.fn() }),
    useLocalSearchParams: () => ({}),
    Link: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  };
});
const mockGetConversation = jest.fn();
jest.mock('../lib/api-client', () => ({
  getConversation: (...a: unknown[]) => mockGetConversation(...a),
  streamMessage: jest.fn(),
  stopStream: jest.fn(),
  getSurfaceCopy: jest.fn().mockResolvedValue({}),
}));

import type { Message } from '@tyndale/shared';

import { ChatComposer } from '../components/chat/ChatComposer';
import { ChatMessage } from '../components/chat/ChatMessage';
import { ChatThread } from '../components/chat/ChatThread';
import { FreeformOpener } from '../components/chat/FreeformOpener';

describe('create-case CTA', () => {
  beforeEach(() => mockPush.mockReset());

  it('renders the button when the action rides the citations (the live-path shape)', () => {
    const msg: Message = {
      message_id: 'a1', conversation_id: 'c1', sequence_number: 2, role: 'assistant',
      content: "Let's get your case started — tap below to upload your bill.",
      content_chunks: [{ tier: 'A', text: "Let's get your case started — tap below to upload your bill.", citations: [] }],
      citations: [{ action_type: 'create_case_cta', title: 'Create a case' }],
      status: 'complete', created_at: new Date().toISOString(),
    };
    const { getByText } = render(
      <ChatMessage message={msg} conversationId="c1" onCitation={() => undefined} />,
    );
    fireEvent.press(getByText(/Upload documents/));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/upload', params: { fromConversation: 'c1' } });
  });
});

describe('upload a bill anytime', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockGetConversation.mockReset();
  });

  it('the composer shows the attach control and calls back on press', () => {
    const onAttach = jest.fn();
    const { getByTestId } = render(
      <ChatComposer onSend={() => undefined} onStop={() => undefined} streaming={false} onAttach={onAttach} />,
    );
    fireEvent.press(getByTestId('composer-attach'));
    expect(onAttach).toHaveBeenCalled();
  });

  it('freeform thread: attach opens a NEW case with the conversation preserved', async () => {
    mockGetConversation.mockResolvedValue({ case_id: null, messages: [] });
    const { getByTestId } = render(<ChatThread conversationId="c1" />);
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    fireEvent.press(getByTestId('composer-attach'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/upload', params: { fromConversation: 'c1' } });
  });

  it('per-case thread: attach routes to THIS case', async () => {
    mockGetConversation.mockResolvedValue({ case_id: 'k1', messages: [] });
    const { getByTestId } = render(<ChatThread conversationId="c2" />);
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    await waitFor(() => {
      fireEvent.press(getByTestId('composer-attach'));
      expect(mockPush).toHaveBeenCalledWith({ pathname: '/upload', params: { caseId: 'k1' } });
    });
  });

  it('the opener offers "upload it" without a second chip row', () => {
    const { getByTestId, getAllByRole } = render(
      <FreeformOpener onChip={() => undefined} copy={{}} conversationId="c1" />,
    );
    fireEvent.press(getByTestId('opener-upload'));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/upload', params: { fromConversation: 'c1' } });
    expect(getAllByRole('button')).toHaveLength(5); // four chips + the one upload link
  });
});
