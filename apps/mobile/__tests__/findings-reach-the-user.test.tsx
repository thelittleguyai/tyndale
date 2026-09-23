/**
 * M1 (e2e 2026-09-23): findings reach the user. The thread's finding + game-plan cards draw
 * what the server projects (no local copy, no local sequencing), and the results surfaces show
 * every finding — error findings in full, context under an explicit "N more notes" line.
 */
import { fireEvent, render } from '@testing-library/react-native';

import type { FindingMomentPayload, GameplanMomentPayload } from '@tyndale/shared';

import { FindingMoment, GameplanMoment } from '../components/thread/MomentCards';
import { isInformational, notesLabel, splitFindings } from '../lib/findings-split';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({ router: { push: (...a: unknown[]) => mockPush(...a) } }));

const finding = (over: Partial<FindingMomentPayload> = {}): FindingMomentPayload => ({
  variant: 'finding',
  finding_id: 'f1',
  case_file_id: 'cf-1',
  title: 'Dispute the service level billed',
  finding_type: 'provider_side',
  responsible_party: 'provider',
  tier: 'rule_based',
  voice_tier: 'B',
  amount: 660,
  amount_line: null,
  claim: 'Anesthesia is billed by the surgery performed.',
  citations: [{ authority: 'CMS Anesthesia Guidelines', section: '§50', src_id: 'src_a1', marker: '[CMS Anesthesia Guidelines, src_a1]' }],
  what_to_do: 'Ask the surgery center to rebill the anesthesia under 01382.',
  worth_checking: null,
  source_line: 'source: CMS Anesthesia Guidelines §50',
  has_source: true,
  ...over,
});

describe('FindingMoment', () => {
  it('draws the title, who it implicates, the amount, the basis chip, what to do and the grounding line', () => {
    const { getByText, getByTestId } = render(<FindingMoment payload={finding()} />);
    expect(getByTestId('finding-moment-f1')).toBeTruthy();
    expect(getByText('Dispute the service level billed')).toBeTruthy();
    expect(getByText('Your provider')).toBeTruthy();
    expect(getByText('up to $660.00')).toBeTruthy();
    expect(getByText('CMS Anesthesia Guidelines §50')).toBeTruthy();
    expect(getByText(/Ask the surgery center/)).toBeTruthy();
    expect(getByText('source: CMS Anesthesia Guidelines §50')).toBeTruthy();
  });

  it('a finding with no dollar gap shows the honest line, and a downgraded claim shows no claim and no chip', () => {
    const { getByText, queryByText } = render(
      <FindingMoment
        payload={finding({ amount: null, amount_line: 'No dollar change — still worth fixing.', claim: null, citations: [], responsible_party: 'either', worth_checking: 'Worth checking: there may be a rule behind this.', tier: 'fact', voice_tier: 'C' })}
      />,
    );
    expect(getByText('No dollar change — still worth fixing.')).toBeTruthy();
    expect(getByText('Provider or insurer')).toBeTruthy();
    expect(queryByText(/Anesthesia is billed/)).toBeNull();
    expect(getByText(/Worth checking/)).toBeTruthy();
  });
});

describe('GameplanMoment', () => {
  it('is the one link from the thread to the results page — the server names the route', () => {
    const payload: GameplanMomentPayload = { variant: 'gameplan', headline: 'Your game plan is ready.', cta: 'See your game plan', next_route: '/audit/cf-1' };
    const { getByTestId, getByText } = render(<GameplanMoment payload={payload} />);
    expect(getByText('Your game plan is ready.')).toBeTruthy();
    fireEvent.press(getByTestId('gameplan-moment-cta'));
    expect(mockPush).toHaveBeenCalledWith('/audit/cf-1');
  });
});

describe('the results surfaces show every finding', () => {
  it('splits error findings from informational context — never hides the context silently', () => {
    const findings = [
      { category: 'upcoding', facts: { gap: 660 } },
      { category: 'cost_sharing_audit', facts: {} },
      { category: 'diagnostic_audit_clean', facts: {} },
      { category: 'diagnostic_audit_clean', facts: { gap: 50 } }, // a "clean" note that claims money is NOT context
      { category: 'phantom_service', presentation: 'informational_context', facts: {} },
      { category: 'duplicate', dollar_impact: 120 },
    ];
    const { errors, notes } = splitFindings(findings);
    expect(errors.map((f) => f.category)).toEqual(['upcoding', 'diagnostic_audit_clean', 'duplicate']);
    expect(notes.map((f) => f.category)).toEqual(['cost_sharing_audit', 'diagnostic_audit_clean', 'phantom_service']);
    expect(isInformational({ category: 'other', facts: {} })).toBe(false); // unknown is not informational
    expect(notesLabel(1)).toBe('1 more note');
    expect(notesLabel(2)).toBe('2 more minor notes');
  });
});
