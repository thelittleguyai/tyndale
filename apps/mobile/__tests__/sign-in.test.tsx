/** Sign-in (2026-08-22, item 2): instant busy feedback on the Google button, consent-URL
 *  prefetch on mount with a re-fetch fallback, one automatic retry, and a working error path. */

import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { Linking } from 'react-native';

const mockGetGoogleAuthUrl = jest.fn();
jest.mock('../lib/api-client', () => ({
  getGoogleAuthUrl: (...a: unknown[]) => mockGetGoogleAuthUrl(...a),
}));
jest.mock('../lib/auth', () => ({ requestEmailMagicLink: jest.fn().mockResolvedValue(undefined) }));
jest.mock('../lib/analytics', () => ({ track: jest.fn() }));
jest.mock('react-native-svg', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { SvgXml: (props: unknown) => React.createElement(View, props as object) };
});

import SignInScreen from '../app/(auth)/sign-in';

const URL = 'https://accounts.google.com/o/oauth2/v2/auth?state=abc';

describe('Google sign-in', () => {
  let openURL: jest.SpyInstance;
  beforeEach(() => {
    mockGetGoogleAuthUrl.mockReset();
    openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as never);
  });
  afterEach(() => openURL.mockRestore());

  it('prefetches the consent URL on mount and the click is a pure redirect', async () => {
    mockGetGoogleAuthUrl.mockResolvedValue(URL);
    const { getByTestId } = render(<SignInScreen />);
    await waitFor(() => expect(mockGetGoogleAuthUrl).toHaveBeenCalledTimes(1));
    fireEvent.press(getByTestId('google-signin'));
    await waitFor(() => expect(openURL).toHaveBeenCalledWith(URL));
    expect(mockGetGoogleAuthUrl).toHaveBeenCalledTimes(1); // no second round trip on click
  });

  it('shows the busy state the instant the button is pressed', async () => {
    let resolve!: (u: string) => void;
    mockGetGoogleAuthUrl.mockImplementation(() => new Promise<string>((r) => (resolve = r)));
    const { getByTestId, getByText, queryByText } = render(<SignInScreen />);
    expect(getByText('Continue with Google')).toBeTruthy();
    fireEvent.press(getByTestId('google-signin'));
    // Synchronous feedback: spinner + label, before the URL ever resolves.
    expect(getByText('Opening Google…')).toBeTruthy();
    expect(getByTestId('google-spinner')).toBeTruthy();
    expect(queryByText('Continue with Google')).toBeNull();
    await act(async () => resolve(URL));
    await waitFor(() => expect(openURL).toHaveBeenCalledWith(URL));
  });

  it('retries once automatically, then surfaces a retryable error', async () => {
    mockGetGoogleAuthUrl.mockRejectedValue(new Error('login init failed: 503'));
    const { getByTestId, findByText, getByText } = render(<SignInScreen />);
    await waitFor(() => expect(mockGetGoogleAuthUrl).toHaveBeenCalledTimes(2)); // mount: try + retry
    fireEvent.press(getByTestId('google-signin'));
    await findByText(/Could not start Google sign-in/); // click: try + retry, then the error
    expect(mockGetGoogleAuthUrl).toHaveBeenCalledTimes(4);
    expect(getByText('Continue with Google')).toBeTruthy(); // button is back, retry works
    mockGetGoogleAuthUrl.mockResolvedValue(URL);
    fireEvent.press(getByTestId('google-signin'));
    await waitFor(() => expect(openURL).toHaveBeenCalledWith(URL));
  });
});
