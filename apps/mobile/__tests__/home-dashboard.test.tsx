/**
 * Homescreen honest subset (Brock mockups): (a) fresh user renders the honest empty state
 * with the check-a-bill CTA and no unbuilt-feature claims; (c) the check-in card's route
 * chips persist via the call-outcome path. (b) pills are covered in home-case-pills.test.
 */
import { fireEvent, render, waitFor, within } from '@testing-library/react-native';

import DashboardScreen from '../app/(app)/index';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush, replace: jest.fn() }) }));
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
const mockGetSurfaceCopy = jest.fn();
const mockRecordCallOutcome = jest.fn().mockResolvedValue(undefined);
const mockSubmitFeedback = jest.fn().mockResolvedValue({});
jest.mock('../lib/api-client', () => ({
  getDashboard: () => mockGetDashboard(),
  getRecord: jest.fn().mockResolvedValue(null),
  getProfileState: jest.fn().mockResolvedValue({ first_name: 'Amy', last_name: null }),
  getUserProfile: jest.fn().mockResolvedValue({ user_type: 'member' }),
  listConversations: jest.fn().mockResolvedValue({ conversations: [] }),
  createConversation: jest.fn().mockResolvedValue({ conversation_id: 'c1' }),
  getSurfaceCopy: () => mockGetSurfaceCopy(),
  submitFeedback: (...a: unknown[]) => mockSubmitFeedback(...a),
  recordCallOutcome: (...a: unknown[]) => mockRecordCallOutcome(...a),
  makeFeedbackEvent: (p: object) => ({ event_id: 'e', timestamp: 't', ...p }),
  removeCase: jest.fn(),
}));

beforeEach(() => {
  mockGetDashboard.mockReset();
  mockGetSurfaceCopy.mockReset();
  mockGetSurfaceCopy.mockResolvedValue({});
  mockPush.mockClear();
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

// ─── doc 40 §D: intake_mode routing + guided surface visibility (data, not code) ────────────
describe('guided mode', () => {
  const guided = {
    ...base,
    intake_mode: 'guided',
    hidden_surfaces: ['freeform_chat_entry', 'quick_actions_grid'], // the provisional default
    guided_resume_case_id: null,
  };

  it('chat-first: nothing changes — every entry point is there and "Check a bill" opens upload', async () => {
    mockGetDashboard.mockResolvedValue({ ...base, intake_mode: 'chat_first', hidden_surfaces: [] });
    const { getByTestId } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('quick-actions-grid')).toBeTruthy());
    expect(within(getByTestId('quick-actions-grid')).getByText('Chat with Tyndale')).toBeTruthy();
    expect(getByTestId('floating-chat')).toBeTruthy();
    fireEvent.press(getByTestId('header-check-bill'));
    expect(mockPush).toHaveBeenCalledWith('/upload');
  });

  it('an older server (no intake_mode in the payload) reads as chat-first', async () => {
    mockGetDashboard.mockResolvedValue(base);
    const { getByTestId } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('quick-actions-grid')).toBeTruthy());
    fireEvent.press(getByTestId('header-check-bill'));
    expect(mockPush).toHaveBeenCalledWith('/upload');
  });

  it('guided: hidden surfaces are ABSENT (never disabled) and "Check a bill" enters /intake', async () => {
    mockGetDashboard.mockResolvedValue(guided);
    const { getByTestId, queryByTestId, queryByText } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('banner-title')).toBeTruthy());
    expect(queryByTestId('quick-actions-grid')).toBeNull();
    expect(queryByTestId('floating-chat')).toBeNull();
    expect(queryByText('Chat with Tyndale')).toBeNull();
    fireEvent.press(getByTestId('header-check-bill')); // still the way in — never a dead end
    expect(mockPush).toHaveBeenCalledWith('/intake');
  });

  it('the hidden set is DATA: a guided user with nothing hidden keeps the grid, pointed at /intake', async () => {
    mockGetDashboard.mockResolvedValue({ ...guided, hidden_surfaces: [] });
    const { getByTestId } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('quick-actions-grid')).toBeTruthy());
    expect(getByTestId('floating-chat')).toBeTruthy();
    fireEvent.press(within(getByTestId('quick-actions-grid')).getByText('Check a bill'));
    expect(mockPush).toHaveBeenCalledWith('/intake');
  });

  it('an unfinished guided case shows the resume card — registry words, straight back into that case', async () => {
    mockGetSurfaceCopy.mockResolvedValue({
      resume_title: 'Pick up where you left off.',
      resume_body: 'Your bill check is saved. A few more steps and I can run it.',
      resume_primary: 'Keep going',
    });
    mockGetDashboard.mockResolvedValue({ ...guided, guided_resume_case_id: 'cf-9' });
    const { getByTestId, getByText } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('guided-resume-card')).toBeTruthy());
    expect(getByText('Pick up where you left off.')).toBeTruthy();
    fireEvent.press(getByTestId('guided-resume-go'));
    expect(mockPush).toHaveBeenCalledWith('/intake?case=cf-9');
  });

  it('holds no guided copy of its own: without the registry strings the card is absent, not improvised', async () => {
    mockGetDashboard.mockResolvedValue({ ...guided, guided_resume_case_id: 'cf-9' });
    const { getByTestId, queryByTestId } = render(<DashboardScreen />);
    await waitFor(() => expect(getByTestId('banner-title')).toBeTruthy());
    expect(queryByTestId('guided-resume-card')).toBeNull();
    expect(getByTestId('header-check-bill')).toBeTruthy(); // the same case opens from here
  });
});

