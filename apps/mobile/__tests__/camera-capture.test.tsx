/**
 * Camera capture — the surface-level rules (N1 · C1).
 *
 * The capture flow itself is DOM-bound (getUserMedia + canvas) and web-only, so it isn't rendered
 * here — same split as the insurance-card upload, whose pure logic is tested in profile.test.tsx
 * while its web component isn't. What IS asserted here is the rule that has to hold on EVERY
 * platform: a build that can't open a camera never offers one.
 */
import { fireEvent, render } from '@testing-library/react-native';

import { CameraCapture, isCaptureSupported } from '../components/upload/CameraCapture';

describe('isCaptureSupported', () => {
  it('is false on a native build — expo-camera is not installed (DL-44)', () => {
    // The jest preset is jest-expo/ios, so this is the native answer. It is also what an old
    // browser with no mediaDevices returns, and both lead to the same picker-only screen.
    expect(isCaptureSupported()).toBe(false);
  });
});

describe('CameraCapture where no camera exists', () => {
  it('renders the hand-off to the picker instead of a viewfinder', () => {
    const { getByTestId, queryByTestId } = render(
      <CameraCapture onDone={jest.fn()} onClose={jest.fn()} />,
    );
    expect(getByTestId('capture-unavailable')).toBeTruthy();
    // No shutter, no framing guide, no review controls — nothing that implies a camera.
    expect(queryByTestId('capture-shutter')).toBeNull();
    expect(queryByTestId('camera-capture')).toBeNull();
  });

  it('offers one way out and does not ask again', () => {
    const onClose = jest.fn();
    const { getByTestId } = render(<CameraCapture onDone={jest.fn()} onClose={onClose} />);
    fireEvent.press(getByTestId('capture-dismiss'));
    expect(onClose).toHaveBeenCalled();
  });

  it('never calls onDone without a capture — an empty upload is not a silent success', () => {
    const onDone = jest.fn();
    render(<CameraCapture onDone={onDone} onClose={jest.fn()} />);
    expect(onDone).not.toHaveBeenCalled();
  });
});
