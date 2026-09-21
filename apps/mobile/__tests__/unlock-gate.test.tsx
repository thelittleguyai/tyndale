/**
 * The unlock moment under unlock_gate_mode (doc 40 open question 2 — PROVISIONAL, Phil decides).
 * The SERVER says whether the moment proceeds; the card draws a way in only when there is one.
 * Billing stays dark: no mode here renders a price the server did not send, or a dead button.
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { UnlockMomentPayload } from '@tyndale/shared';

import { UnlockMoment } from '../components/thread/MomentCards';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ router: { push: (...a: unknown[]) => mockPush(...a) } }));

const base: UnlockMomentPayload = {
  variant: 'first_case_unlock',
  headline: 'Here is the plan to fix it.',
  value_points: ['A step-by-step plan', 'Scripts for each call'],
  footnote: "It's free while we're in beta.",
};

beforeEach(() => mockPush.mockClear());

it('free_beta: the moment proceeds — one button, the server’s label, the server’s route', () => {
  const { getByTestId, getByText } = render(
    <UnlockMoment payload={{ ...base, gate_mode: 'free_beta', proceeds: true, proceed_label: 'See my plan', next_route: '/case/cf-1' }} />,
  );
  expect(getByText("It's free while we're in beta.")).toBeTruthy();
  fireEvent.press(getByTestId('unlock-proceed'));
  expect(mockPush).toHaveBeenCalledWith('/case/cf-1');
});

it.each(['block', 'billing'] as const)('%s: no way in is drawn — absent, never a dead button', (gate_mode) => {
  const { queryByTestId } = render(<UnlockMoment payload={{ ...base, gate_mode, proceeds: false, proceed_label: null, next_route: null }} />);
  expect(queryByTestId('unlock-proceed')).toBeNull();
});

it('an older server (no gate fields) renders the card as before, with no button', () => {
  const { queryByTestId, getByText } = render(<UnlockMoment payload={base} />);
  expect(getByText('Here is the plan to fix it.')).toBeTruthy();
  expect(queryByTestId('unlock-proceed')).toBeNull();
});
