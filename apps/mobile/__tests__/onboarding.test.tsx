import { fireEvent, render, waitFor } from '@testing-library/react-native';

// onboarding.tsx gained a Phase-3.4 auth guard: it imports Redirect + useCurrentUser and,
// with no signed-in user, renders <Redirect href="/sign-in" />. The old mock omitted Redirect
// (→ "Element type is invalid") and left useCurrentUser real (→ no user in jest → it took the
// Redirect path instead of the form). Mock both so the FORM renders and the gating asserts run.
jest.mock('expo-router', () => ({
  router: { replace: jest.fn(), push: jest.fn() },
  Redirect: () => null,
}));
jest.mock('../lib/auth', () => ({
  useCurrentUser: () => ({ user: { user_id: 'u1', first_name: 'Jane' }, loading: false }),
}));
jest.mock('../lib/api-client', () => ({
  __esModule: true,
  getProfileState: jest.fn().mockResolvedValue({
    profile_completed: false,
    email: 'x@y.com',
    first_name: null,
    last_name: null,
    date_of_birth: null,
    phone: null,
    has_insurance_card: false,
  }),
  patchProfile: jest.fn().mockResolvedValue({ profile_completed: true }),
  uploadInsuranceCard: jest.fn(),
}));

import Onboarding from '../app/onboarding';
import { patchProfile } from '../lib/api-client';

describe('Onboarding gating (CO-17)', () => {
  const y = new Date().getFullYear();

  it('enables Continue only after first + last name, a valid 18+ DOB, and reviewed terms', async () => {
    const screen = render(<Onboarding />);
    const { getByText, getByPlaceholderText } = screen;

    // Disabled at first — pressing Continue does nothing.
    fireEvent.press(getByText('Continue to Tyndale'));
    expect(patchProfile).not.toHaveBeenCalled();

    fireEvent.changeText(getByPlaceholderText('Jane'), 'Jane');
    fireEvent.changeText(getByPlaceholderText('Doe'), 'Doe');
    fireEvent.changeText(getByPlaceholderText('MM/DD/YYYY'), `04/15/${y - 30}`);

    // Terms checkbox is locked until the user opens "Review Terms".
    fireEvent.press(getByText(/I agree to the Terms/));
    fireEvent.press(getByText('Continue to Tyndale'));
    expect(patchProfile).not.toHaveBeenCalled(); // still locked — terms not reviewed

    fireEvent.press(getByText('Review Terms of Service'));
    fireEvent.press(getByText(/I agree to the Terms/)); // now allowed -> checked

    fireEvent.press(getByText('Continue to Tyndale'));
    await waitFor(() => expect(patchProfile).toHaveBeenCalled());
    const arg = (patchProfile as jest.Mock).mock.calls[0][0];
    expect(arg).toMatchObject({
      first_name: 'Jane',
      last_name: 'Doe',
      date_of_birth: `${y - 30}-04-15`,
      accept_terms: true,
    });
  });
});
