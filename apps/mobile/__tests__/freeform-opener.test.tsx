/** Item 4 (Brock 2026-08-22): an empty freeform conversation renders the scripted opener +
 *  four chips; tapping a chip sends it as the first user message. */

import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockGetConversation = jest.fn();
const mockStreamMessage = jest.fn();
const mockGetSurfaceCopy = jest.fn();
jest.mock('../lib/api-client', () => ({
  getConversation: (...a: unknown[]) => mockGetConversation(...a),
  streamMessage: (...a: unknown[]) => mockStreamMessage(...a),
  stopStream: jest.fn(),
  getSurfaceCopy: (...a: unknown[]) => mockGetSurfaceCopy(...a),
}));

import { ChatThread } from '../components/chat/ChatThread';
import { FreeformOpener, splitChips } from '../components/chat/FreeformOpener';

describe('FreeformOpener', () => {
  it('renders the opener and exactly four chips from the seed copy', () => {
    const onChip = jest.fn();
    const { getByText } = render(<FreeformOpener onChip={onChip} copy={{}} />);
    expect(getByText('What can I help you with today?')).toBeTruthy();
    for (const chip of ['Understand a bill', 'Check if a bill is correct', "Think I'm overcharged", 'Something else']) {
      expect(getByText(chip)).toBeTruthy();
    }
    fireEvent.press(getByText("Think I'm overcharged"));
    expect(onChip).toHaveBeenCalledWith("Think I'm overcharged");
  });

  it('uses registry copy when the surface serves it, and caps chips at four', () => {
    const { getByText, queryByText } = render(
      <FreeformOpener
        onChip={() => undefined}
        copy={{ opener: 'Brock-authored line', opener_chips: 'A · B · C · D · E' }}
      />,
    );
    expect(getByText('Brock-authored line')).toBeTruthy();
    expect(getByText('D')).toBeTruthy();
    expect(queryByText('E')).toBeNull();
    expect(splitChips(null)).toHaveLength(4);
  });
});

describe('empty conversation', () => {
  beforeEach(() => {
    mockGetConversation.mockReset();
    mockStreamMessage.mockReset();
    mockGetSurfaceCopy.mockResolvedValue({});
    mockStreamMessage.mockImplementation(async (_id: string, _c: string, onEvent: (e: unknown) => void) => {
      onEvent({ event: 'done', data: {} });
    });
  });

  it('renders the opener with chips and a tap becomes the first user message', async () => {
    mockGetConversation.mockResolvedValue({ messages: [] });
    const { findByText } = render(
      <ChatThread conversationId="c1" emptyState={(send) => <FreeformOpener onChip={send} />} />,
    );
    const chip = await findByText('Understand a bill');
    fireEvent.press(chip);
    await waitFor(() => expect(mockStreamMessage).toHaveBeenCalled());
    expect(mockStreamMessage.mock.calls[0][1]).toBe('Understand a bill');
  });
});
