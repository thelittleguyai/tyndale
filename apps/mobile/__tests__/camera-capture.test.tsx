/**
 * Camera capture — platform truths (N1 · C1).
 *
 * Rewritten 2026-08-17 when the worklets removal made native capture REAL: the jest preset is
 * jest-expo/ios, so this file exercises `CameraCapture.native.tsx` (Metro/jest resolve the
 * .native module). The prior version of this file asserted natively-unsupported — that world
 * is gone. The honesty rules carry over unchanged: no "Looks readable" badge exists to test,
 * permission-denied hands off to the picker without nagging, and nothing calls onDone without
 * a capture.
 */
import { fireEvent, render } from '@testing-library/react-native';
import { useCameraPermissions } from 'expo-camera';

import { CameraCapture, isCaptureSupported } from '../components/upload/CameraCapture';

const mockPermissions = useCameraPermissions as jest.Mock;

describe('isCaptureSupported (native)', () => {
  it('is true — DL-44 fell and expo-camera is installed', () => {
    expect(isCaptureSupported()).toBe(true);
  });
});

describe('CameraCapture (native)', () => {
  it('renders the live viewfinder with a shutter when permission is granted', () => {
    const { getByTestId, queryByTestId } = render(
      <CameraCapture onDone={jest.fn()} onClose={jest.fn()} />,
    );
    expect(getByTestId('camera-capture')).toBeTruthy();
    expect(getByTestId('capture-shutter')).toBeTruthy();
    // No badge, no review chrome before a capture exists.
    expect(queryByTestId('capture-keep')).toBeNull();
    expect(queryByTestId('capture-warning')).toBeNull();
  });

  it('permission denied → one ask + the picker hand-off, no viewfinder', () => {
    mockPermissions.mockReturnValueOnce([{ granted: false, canAskAgain: true }, jest.fn()]);
    const onClose = jest.fn();
    const { getByTestId, queryByTestId } = render(
      <CameraCapture onDone={jest.fn()} onClose={onClose} />,
    );
    expect(getByTestId('capture-unavailable')).toBeTruthy();
    expect(getByTestId('capture-request-permission')).toBeTruthy();
    expect(queryByTestId('capture-shutter')).toBeNull();
    fireEvent.press(getByTestId('capture-dismiss'));
    expect(onClose).toHaveBeenCalled();
  });

  it('permanently denied → no re-ask button, just the honest hand-off', () => {
    mockPermissions.mockReturnValueOnce([{ granted: false, canAskAgain: false }, jest.fn()]);
    const { getByTestId, queryByTestId } = render(
      <CameraCapture onDone={jest.fn()} onClose={jest.fn()} />,
    );
    expect(getByTestId('capture-unavailable')).toBeTruthy();
    expect(queryByTestId('capture-request-permission')).toBeNull();
  });

  it('never calls onDone without a capture', () => {
    const onDone = jest.fn();
    render(<CameraCapture onDone={onDone} onClose={jest.fn()} />);
    expect(onDone).not.toHaveBeenCalled();
  });
});
