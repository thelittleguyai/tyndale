/**
 * The /intake controller (doc 40): ONE route. It asks the server's planner what to draw, draws
 * it, and sends the answer back — no sequence, no product copy, no affordance with nothing
 * behind it.
 */
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import type { IntakeStateResponse } from '@tyndale/shared';

import IntakeScreenRoute from '../app/intake/index';

const mockReplace = jest.fn();
const mockPush = jest.fn();
let mockParams: { case?: string; screen?: string } = {};
jest.mock('expo-router', () => {
  const React = jest.requireActual('react');
  return {
    router: { replace: (...a: unknown[]) => mockReplace(...a), push: (...a: unknown[]) => mockPush(...a) },
    useLocalSearchParams: () => mockParams,
    // focus == mount in a unit test
    useFocusEffect: (cb: () => void) => React.useEffect(cb, [cb]),
  };
});
jest.mock('react-native-svg', () => ({ SvgXml: () => null }));

const mockGetIntakeState = jest.fn();
const mockStartIntake = jest.fn();
const mockAnswerIntake = jest.fn();
const mockRunIntake = jest.fn();
const mockHandoffIntake = jest.fn();
jest.mock('../lib/api-client', () => ({
  getIntakeState: (...a: unknown[]) => mockGetIntakeState(...a),
  startIntake: (...a: unknown[]) => mockStartIntake(...a),
  answerIntake: (...a: unknown[]) => mockAnswerIntake(...a),
  runIntake: (...a: unknown[]) => mockRunIntake(...a),
  handoffIntake: (...a: unknown[]) => mockHandoffIntake(...a),
  emailIntakeHelp: jest.fn(),
  attestCase: jest.fn(),
  declineAttest: jest.fn(),
  confirmPlanProposal: jest.fn(),
  rejectPlanProposal: jest.fn(),
}));

const GROUPS = ['bill', 'card', 'plan_rules', 'eob', 'timeline', 'about_you', 'confirmations'] as const;
const chrome = { save_exit: 'Save and exit', see_example: 'See an example', help_find: 'Help me find it', close: 'Close', retry: 'Try again', load_error: "I couldn't load this.", save_error: "That didn't save." };
type ScreenOver = Partial<IntakeStateResponse['screen']>;
const state = (screen: ScreenOver, over: Partial<Omit<IntakeStateResponse, 'screen'>> = {}): IntakeStateResponse => ({
  case_file_id: 'cf-1',
  intake_status: 'in_progress',
  intake_mode: 'guided',
  current_step: screen.id ?? 'x',
  completed_steps: [],
  progress: { segments: GROUPS.map((g) => ({ group: g, filled: false, label: g })), filled: 0, total: 7, line: null, note: null, glosses: {}, high_water: [] },
  chrome,
  resume: null,
  captured_data: { coverage: {}, bills_count: 0, eobs_count: 0, visit_context: null, coverage_regime: null, regime_detection: null },
  missing_items: [],
  ...over,
  screen: { id: 'x', kind: 'info', progress_group: null, copy: {}, data: {}, skippable: false, ...screen },
});

const planRules = (extra: ScreenOver = {}) =>
  state({ id: 'plan_rules', kind: 'capture', progress_group: 'plan_rules', skippable: true, data: { expect: 'sbc', have: 0, note: null }, copy: { title: 'Your plan rules', primary: 'Add my plan summary', skip: "I don't have it", skip_consequence: 'I will use typical plan rules.' }, ...extra });

beforeEach(() => {
  [mockReplace, mockPush, mockGetIntakeState, mockStartIntake, mockAnswerIntake, mockRunIntake, mockHandoffIntake].forEach((m) => m.mockReset());
  mockParams = { case: 'cf-1' };
});

it('draws the screen the planner picked, with the registry title', async () => {
  mockGetIntakeState.mockResolvedValue(planRules());
  const { getByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-title').props.children).toBe('Your plan rules'));
  expect(mockGetIntakeState).toHaveBeenCalledWith('cf-1', { screen: undefined });
});

it('offers "See an example" / "Help me find it" ONLY when the server sent something to show', async () => {
  mockGetIntakeState.mockResolvedValue(planRules()); // asset: null server-side → no `example` key at all
  const bare = render(<IntakeScreenRoute />);
  await waitFor(() => expect(bare.getByTestId('intake-title')).toBeTruthy());
  expect(bare.queryByTestId('intake-see-example')).toBeNull();
  expect(bare.queryByTestId('intake-help')).toBeNull();
  bare.unmount();

  mockGetIntakeState.mockResolvedValue(
    planRules({
      example: { ask: 'sbc', title: 'A sample plan summary', callouts: ['Look for the deductible.'], asset: { kind: 'external_pdf', url: 'https://www.cms.gov/sample.pdf', publisher: 'CMS' }, source_line: 'A federal sample.', glosses: {} },
      help: { document_type: 'sbc', scope: 'generic', payer_name: null, title: 'How to find it', note: 'These steps work for most plans.', steps: ['Log in to your plan website.'], verified: true, can_email: true },
    }),
  );
  const full = render(<IntakeScreenRoute />);
  await waitFor(() => expect(full.getByTestId('intake-see-example')).toBeTruthy());
  expect(full.getByTestId('intake-help')).toBeTruthy();
});

it('sends an answer back and draws whatever the planner returns next — the app holds no sequence', async () => {
  mockGetIntakeState.mockResolvedValue(planRules());
  mockAnswerIntake.mockResolvedValue(state({ id: 'plan_year', kind: 'choice', copy: { title: 'When does your plan year start?' }, data: { options: [] } }));
  const { getByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-skip')).toBeTruthy());
  fireEvent.press(getByTestId('intake-skip'));
  await waitFor(() => expect(getByTestId('intake-title').props.children).toBe('When does your plan year start?'));
  expect(mockAnswerIntake).toHaveBeenCalledWith('cf-1', 'plan_rules', 'skip', {});
});

it('a capture goes through the EXISTING upload flow and comes back to this case', async () => {
  mockGetIntakeState.mockResolvedValue(planRules());
  const { getByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-capture')).toBeTruthy());
  fireEvent.press(getByTestId('intake-capture'));
  expect(mockPush).toHaveBeenCalledWith({ pathname: '/upload', params: { caseId: 'cf-1', expect: 'sbc', returnTo: '/intake?case=cf-1' } });
});

it('READY: runs the audit ONCE and hands off to the existing results surface (§C2)', async () => {
  mockGetIntakeState.mockResolvedValue(state({ id: 'READY', kind: 'ready', copy: { title: 'Checking your bill' } }));
  mockRunIntake.mockResolvedValue({ case_file_id: 'cf-1', status: 'audit_running', next_route: '/case/cf-1' });
  render(<IntakeScreenRoute />);
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/case/cf-1'));
  expect(mockRunIntake).toHaveBeenCalledTimes(1);
});

it('a hand-off asks the SERVER where chat-first picks the case up — and closes the guided route', async () => {
  mockGetIntakeState.mockResolvedValue(
    state({ id: 'handoff', kind: 'handoff', copy: { title: "Let's finish this in chat.", body: 'For Medicare, I check your bill in our chat. Nothing you added is lost.', primary: 'Go to chat' } }),
  );
  mockHandoffIntake.mockResolvedValue({ case_file_id: 'cf-1', status: 'open', next_route: '/audit/cf-1/thread', conversation_id: 'conv-1' });
  const { getByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-handoff')).toBeTruthy());
  fireEvent.press(getByTestId('intake-handoff'));
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/audit/cf-1/thread'));
  expect(mockHandoffIntake).toHaveBeenCalledWith('cf-1');
});

it('landing with saved work shows "pick up where you left off" and the REAL link lifetime', async () => {
  mockParams = {};
  mockGetIntakeState.mockResolvedValue(
    state(planRules().screen, { resume: { case_file_id: 'cf-1', title: 'Pick up where you left off.', body: 'Your work is saved. Next up: your plan rules.', primary: 'Keep going', new: 'Start a new bill', link_expiry: 'To come back, ask for a new sign-in link. Each link works for 15 minutes.' } }),
  );
  const { getByTestId, getByText, queryByText, queryByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-resume')).toBeTruthy());
  expect(getByText(/15 minutes/)).toBeTruthy();
  expect(queryByText(/90 days/)).toBeNull();
  expect(queryByTestId('intake-title')).toBeNull();
  fireEvent.press(getByTestId('intake-resume-continue'));
  expect(getByTestId('intake-title').props.children).toBe('Your plan rules');
});

it('a failed load offers a retry, never a blank screen', async () => {
  mockGetIntakeState.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(planRules());
  const { getByTestId } = render(<IntakeScreenRoute />);
  await waitFor(() => expect(getByTestId('intake-retry')).toBeTruthy());
  fireEvent.press(getByTestId('intake-retry'));
  await waitFor(() => expect(getByTestId('intake-title')).toBeTruthy());
});
