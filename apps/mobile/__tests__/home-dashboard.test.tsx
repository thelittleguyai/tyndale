/**
 * Homescreen honest subset (Brock mockups): (a) fresh user renders the honest empty state
 * with the check-a-bill CTA and no unbuilt-feature claims; (c) the check-in card's route
 * chips persist via the call-outcome path. (b) pills are covered in home-case-pills.test.
 */
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import DashboardScreen from '../app/(app)/index';

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }));
jest.mock('react-native-svg', () => ({ SvgXml: () => null }));
jest.mock('../lib/auth', () => ({ useSignOut: () => jest.fn() }));
jest.mock('../lib/intake-deferred', () => ({ clearIntakeDeferred: jest.fn() }));

const base = {
  user: { id: 'u1', first_name: 'Amy' },
  banner: { title: 'Welcome back, Amy.', subline: 'Ready when you are — check a bill and I’ll take it from there.' },
  coverage: { deductible: null, oop_max: null, copays: null, extraction_status: 'missing' },
  amount_saved_ytd: 0,
  recovered_to_date: 0,
  open_count: 0,
  needs_you_count: 0,
  coverage_connection_enabled: false,
  intake_status: 'complete',
  intake_current_step: null,
  has_cases: false,
  open_cases: [],
  active_cases: [],
  outcome_prompts: [] as object[],
  status_forward_greeting: null,
  record_enabled: false,
};

const mockGetDashboard = jest.fn();
const mockRecordCallOutcome = jest.fn().mockResolvedValue(undefined);
const mockSubmitFeedback = jest.fn().mockResolvedValue({});
jest.mock('../lib/api-client', () => ({
  getDashboard: () => mockGetDashboard(),
  getRecord: jest.fn().mockResolvedValue(null),
  getProfileState: jest.fn().mockResolvedValue({ first_name: 'Amy', last_name: null }),
  getUserProfile: jest.fn().mockResolvedValue({ user_type: 'member' }),
  listConversations: jest.fn().mockResolvedValue({ conversations: [] }),
  createConversation: jest.fn().mockResolvedValue({ conversation_id: 'c1' }),
  getSurfaceCopy: jest.fn().mockResolvedValue({}),
  submitFeedback: (...a: unknown[]) => mockSubmitFeedback(...a),
  recordCallOutcome: (...a: unknown[]) => mockRecordCallOutcome(...a),
  makeFeedbackEvent: (p: object) => ({ event_id: 'e', timestamp: 't', ...p }),
  removeCase: jest.fn(),
}));

beforeEach(() => {
  mockGetDashboard.mockReset();
  mockRecordCallOutcome.mockClear();
  mockSubmitFeedback.mockClear();
});

it('fresh user: honest empty state — neutral recovered card, CTA, no unbuilt claims', async () => {
  mockGetDashboard.mockResolvedValue(base);
  const { getByTestId, getByText, queryByText } = render(<DashboardScreen />);
  await waitFor(() => expect(getByTestId('banner-title').props.children).toBe('Welcome back, Amy.'));
  expect(getByTestId('stat-recovered')).toBeTruthy();
  expect(queryByText('$0')).toBeNull(); // never a sad zero
  expect(getByText(/your confirmed wins land here/)).toBeTruthy();
  expect(getByTestId('header-check-bill')).toBeTruthy();
  expect(getByTestId('floating-chat')).toBeTruthy();
  // banned unbuilt-feature claims (B8) + dead quick actions
  expect(queryByText(/deadlines watched/i)).toBeNull();
  expect(queryByText(/re-checked/i)).toBeNull();
  expect(queryByText('Estimate Costs')).toBeNull();
  expect(queryByText('Find a Doctor')).toBeNull();
  expect(queryByText('Plan a Visit')).toBeNull();
  expect(queryByText('Connect your plan')).toBeNull(); // flag off in dev
});

it('check-in card: a route chip records the call outcome', async () => {
  mockGetDashboard.mockResolvedValue({
    ...base,
    has_cases: true,
    open_count: 1,
    outcome_prompts: [
      { case_file_id: 'cf1', days_since_recommendation: 15, finding_summary: 'the duplicate charge with Blue Shield' },
    ],
  });
  const { getByTestId, getByText } = render(<DashboardScreen />);
  await waitFor(() => expect(getByTestId('checkin-card')).toBeTruthy());
  fireEvent.press(getByTestId('checkin-remind'));
  expect(getByTestId('checkin-context').props.children.join('')).toContain('Blue Shield');
  fireEvent.press(getByText("They're fixing it"));
  await waitFor(() =>
    expect(mockRecordCallOutcome).toHaveBeenCalledWith('cf1', 'dashboard-checkin', 'fixing_it'),
  );
  expect(mockSubmitFeedback).not.toHaveBeenCalled(); // a route is NOT an outcome (H6)
});
