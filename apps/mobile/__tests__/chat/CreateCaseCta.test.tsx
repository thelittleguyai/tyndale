import { fireEvent, render } from '@testing-library/react-native';

// jest allows out-of-scope refs in a mock factory when prefixed with "mock".
const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));

import { CreateCaseCta } from '../../components/chat/CreateCaseCta';

describe('CreateCaseCta', () => {
  it('navigates to upload, preserving the conversation context', () => {
    const { getByText } = render(<CreateCaseCta conversationId="conv-123" />);
    fireEvent.press(getByText(/Upload documents/));
    expect(mockPush).toHaveBeenCalledWith({
      pathname: '/upload',
      params: { fromConversation: 'conv-123' },
    });
  });
});
