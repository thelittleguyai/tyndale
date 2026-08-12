import { fireEvent, render, waitFor } from '@testing-library/react-native';

import type { CaseSummaryPayload, GameplanStep } from '../lib/api-client';
import { CallMode, Gameplan } from '../components/record/Gameplan';

// Per-file: a known case id + a mockable getCaseSummary.
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  useLocalSearchParams: () => ({ case_file_id: 'c1' }),
}));
const mockGetCaseSummary = jest.fn();
jest.mock('../lib/api-client', () => ({
  getCaseSummary: (...a: unknown[]) => mockGetCaseSummary(...a),
}));

import CaseSummaryScreen from '../app/(app)/case/[case_file_id]/index';

function step(over: Partial<GameplanStep> = {}): GameplanStep {
  return {
    index: 1,
    finding_id: 'f1',
    title: 'Fix the cost-sharing math',
    party: 'payer',
    party_label: 'your insurance company',
    dollar_impact: 640,
    script: {
      when_they_pick_up: 'Give your name and member ID.',
      the_problem: 'The payer miscalculated cost-sharing.',
      the_ask: 'Ask them to recompute and reissue the EOB.',
      get_it_in_writing: 'Ask for written confirmation.',
      if_they_push_back: ['Ask for the specific policy.'],
    },
    reference_kind: null,
    reference_number: null,
    phone: null,
    ...over,
  };
}

function summary(over: Partial<CaseSummaryPayload> = {}): CaseSummaryPayload {
  return {
    case_file_id: 'c1',
    status_banner: { status: 'audit_complete', label: 'Results ready', response_deadline: null },
    provider: null,
    service_date: null,
    claim_number: null,
    account_number: null,
    three_number: { provider_billed: 1200, eob_member_responsibility: 1200, tyndale_computed: 560 },
    identified_estimate: 640,
    recovered_so_far: 0,
    findings: [],
    open_items: [],
    next_check_in_date: null,
    gameplan: [step()],
    call_mode_intro: 'One call at a time.',
    call_mode_outro: 'Tell me what they said.',
    ...over,
  };
}

describe('Gameplan', () => {
  it('lists steps biggest-dollar-first and expands to the four call beats', () => {
    const steps = [
      step({ finding_id: 'big', index: 1, title: 'Big charge', dollar_impact: 900 }),
      step({ finding_id: 'small', index: 2, title: 'Small charge', dollar_impact: 200 }),
    ];
    const { getByText, queryByText } = render(<Gameplan steps={steps} />);
    // both titles present; beats hidden until a step is tapped
    expect(getByText('Big charge')).toBeTruthy();
    expect(queryByText('The problem')).toBeNull();
    fireEvent.press(getByText('Big charge'));
    expect(getByText('The problem')).toBeTruthy();
    expect(getByText('The ask')).toBeTruthy();
    expect(getByText('If they push back')).toBeTruthy();
  });

  it('renders nothing when there are no steps', () => {
    const { toJSON } = render(<Gameplan steps={[]} />);
    expect(toJSON()).toBeNull();
  });
});

describe('CallMode step-through', () => {
  it('walks intro → call → outro and closes on Done', () => {
    const onClose = jest.fn();
    const { getByTestId, getByText, queryByText } = render(
      <CallMode steps={[step()]} intro="Get ready to call." outro="Tell me how it went." onClose={onClose} />,
    );
    // intro first
    expect(getByText('Get ready to call.')).toBeTruthy();
    fireEvent.press(getByTestId('call-mode-next')); // → the call
    expect(getByText('Ask them to recompute and reissue the EOB.')).toBeTruthy();
    fireEvent.press(getByTestId('call-mode-next')); // → outro
    expect(getByText('Tell me how it went.')).toBeTruthy();
    expect(queryByText('Next')).toBeNull(); // last page shows Done, not Next
    fireEvent.press(getByTestId('call-mode-done'));
    expect(onClose).toHaveBeenCalled();
  });

  it('closing from the header calls onClose', () => {
    const onClose = jest.fn();
    const { getByTestId } = render(
      <CallMode steps={[step()]} intro="" outro="" onClose={onClose} />,
    );
    fireEvent.press(getByTestId('call-mode-close'));
    expect(onClose).toHaveBeenCalled();
  });

  // L7/B4 — the pinned strip. It renders from the step's TYPED fields only, so a number can
  // never reach a phone call without having been extracted from a document first.
  it('pins the typed reference for the party being called', () => {
    const { getByText } = render(
      <CallMode
        steps={[step({ reference_kind: 'claim', reference_number: 'TST20260514' })]}
        intro=""
        outro=""
        onClose={jest.fn()}
      />,
    );
    expect(getByText(/Claim #\s*TST20260514/)).toBeTruthy();
  });

  it('labels a provider call with the account number instead', () => {
    const { getByText } = render(
      <CallMode
        steps={[
          step({
            party: 'provider',
            party_label: "the provider's billing office",
            reference_kind: 'account',
            reference_number: '1821709',
          }),
        ]}
        intro=""
        outro=""
        onClose={jest.fn()}
      />,
    );
    expect(getByText(/Account #\s*1821709/)).toBeTruthy();
  });

  it('omits the reference row and the dial button when the documents carried neither', () => {
    const { queryByTestId } = render(
      <CallMode steps={[step()]} intro="" outro="" onClose={jest.fn()} />,
    );
    expect(queryByTestId('call-mode-reference')).toBeNull();
    expect(queryByTestId('call-mode-dial')).toBeNull();
  });

  it('shows tap-to-dial once a typed phone exists', () => {
    const { getByTestId } = render(
      <CallMode steps={[step({ phone: '1-800-555-0142' })]} intro="" outro="" onClose={jest.fn()} />,
    );
    expect(getByTestId('call-mode-dial')).toBeTruthy();
  });
});

describe('CaseSummaryScreen terminal states', () => {
  afterEach(() => mockGetCaseSummary.mockReset());

  it('complete case shows the three-number card and confirmed recovered tally', async () => {
    mockGetCaseSummary.mockResolvedValue(summary({ recovered_so_far: 400 }));
    const { getByText } = render(<CaseSummaryScreen />);
    await waitFor(() => expect(getByText('Your three numbers')).toBeTruthy());
    expect(getByText('What you should owe')).toBeTruthy(); // the row label (now unique)
    expect(getByText('$560')).toBeTruthy(); // tyndale_computed
    expect(getByText('Recovered so far')).toBeTruthy();
    expect(getByText('$400')).toBeTruthy(); // CONFIRMED
  });

  it('needs-documents case shows the checklist and no three-number card', async () => {
    mockGetCaseSummary.mockResolvedValue(
      summary({
        status_banner: { status: 'audit_incomplete', label: 'Needs documents', response_deadline: null },
        three_number: null,
        gameplan: [],
        open_items: [
          { key: 'eob', label: 'Explanation of Benefits (EOB)', how_to_get: 'Ask your insurer.', have: false },
        ],
      }),
    );
    const { getByText, queryByText } = render(<CaseSummaryScreen />);
    await waitFor(() => expect(getByText('To finish, we need')).toBeTruthy());
    expect(getByText('Explanation of Benefits (EOB)')).toBeTruthy();
    expect(getByText('Ask your insurer.')).toBeTruthy();
    expect(queryByText('What you should owe')).toBeNull(); // no {0,0,0} three-number card
  });
});
