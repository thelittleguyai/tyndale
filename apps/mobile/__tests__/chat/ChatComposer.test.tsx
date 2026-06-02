import { fireEvent, render } from '@testing-library/react-native';

import { ChatComposer } from '../../components/chat/ChatComposer';

describe('ChatComposer', () => {
  it('shows send (not stop) when idle and sends the typed text', () => {
    const onSend = jest.fn();
    const { getByLabelText, getByPlaceholderText, queryByLabelText } = render(
      <ChatComposer onSend={onSend} onStop={() => undefined} streaming={false} />,
    );
    expect(getByLabelText('Send message')).toBeTruthy();
    expect(queryByLabelText('Stop generating')).toBeNull();

    fireEvent.changeText(getByPlaceholderText(/Ask about your bill/), 'How do I appeal?');
    fireEvent.press(getByLabelText('Send message'));
    expect(onSend).toHaveBeenCalledWith('How do I appeal?');
  });

  it('shows the stop button while streaming', () => {
    const onStop = jest.fn();
    const { getByLabelText, queryByLabelText } = render(
      <ChatComposer onSend={() => undefined} onStop={onStop} streaming={true} />,
    );
    expect(getByLabelText('Stop generating')).toBeTruthy();
    expect(queryByLabelText('Send message')).toBeNull();
    fireEvent.press(getByLabelText('Stop generating'));
    expect(onStop).toHaveBeenCalled();
  });
});
