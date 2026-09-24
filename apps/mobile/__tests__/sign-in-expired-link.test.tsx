/**
 * The resume path re-issues a fresh link cleanly (Brock 2026-09-21, decision 7). An expired
 * sign-in link lands here with ?link=expired&t=… — one tap renews it to the address inside it
 * (nobody retypes the email); a signed-out visit to /intake arrives with ?return=/intake… and the
 * link it asks for comes back there.
 */
import { fireEvent, render, waitFor } from '@testing-library/react-native';

let mockParams: Record<string, string | undefined> = {};
jest.mock('expo-router', () => ({ useLocalSearchParams: () => mockParams }));
const mockReissue = jest.fn();
jest.mock('../lib/api-client', () => ({
  getGoogleAuthUrl: jest.fn().mockResolvedValue('https://accounts.google.com/x'),
  reissueMagicLink: (...a: unknown[]) => mockReissue(...a),
}));
const mockRequest = jest.fn().mockResolvedValue(undefined);
jest.mock('../lib/auth', () => ({ requestEmailMagicLink: (...a: unknown[]) => mockRequest(...a) }));
jest.mock('../lib/analytics', () => ({ track: jest.fn() }));
jest.mock('react-native-svg', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { SvgXml: (props: unknown) => React.createElement(View, props as object) };
});

import SignInScreen from '../app/(auth)/sign-in';

beforeEach(() => {
  mockReissue.mockReset();
  mockRequest.mockClear();
});

it('an expired link is renewed in one tap, to the address inside it', async () => {
  mockParams = { link: 'expired', t: 'expired.jwt.token' };
  mockReissue.mockResolvedValue({ email_hint: 'j•••@example.com' });
  const r = render(<SignInScreen />);
  expect(r.getByText('That sign-in link has expired.')).toBeTruthy();
  fireEvent.press(r.getByTestId('renew-link'));
  await waitFor(() => expect(r.getByTestId('link-renewed')).toBeTruthy());
  expect(mockReissue).toHaveBeenCalledWith('expired.jwt.token');
  expect(r.getByText('j•••@example.com')).toBeTruthy();
  expect(mockRequest).not.toHaveBeenCalled(); // no typing, no second request
});

it('a link that cannot be renewed falls back to the email field, said plainly', async () => {
  mockParams = { link: 'expired', t: 'forged' };
  mockReissue.mockRejectedValue(new Error('reissue 400'));
  const r = render(<SignInScreen />);
  fireEvent.press(r.getByTestId('renew-link'));
  await waitFor(() => expect(r.getByText(/can't be renewed/)).toBeTruthy());
  expect(r.getByTestId('send-magic-link')).toBeTruthy();
});

it('a sign-in that started on /intake asks for a link that comes back there', async () => {
  mockParams = { return: '/intake?case=cf-1' };
  const r = render(<SignInScreen />);
  expect(r.queryByTestId('link-expired')).toBeNull();
  fireEvent.changeText(r.getByLabelText('Email address'), 'me@example.com');
  fireEvent.press(r.getByTestId('send-magic-link'));
  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('me@example.com', '/intake?case=cf-1'));
});

it('an off-site return value is never sent', async () => {
  mockParams = { return: '//evil.example/phish' };
  const r = render(<SignInScreen />);
  fireEvent.changeText(r.getByLabelText('Email address'), 'me@example.com');
  fireEvent.press(r.getByTestId('send-magic-link'));
  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith('me@example.com', undefined));
});
