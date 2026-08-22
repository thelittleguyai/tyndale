import { render } from '@testing-library/react-native';

import type { FindingOut } from '../lib/api-client';
import { FindingCard } from '../components/audit/FindingCard';

// The card nests a ThumbsRating that submits feedback on press. Stub exactly the value exports
// that subtree imports (types are erased) so the test is about the grounding line only.
jest.mock('../lib/api-client', () => ({
  makeFeedbackEvent: jest.fn(() => ({})),
  submitFeedback: jest.fn().mockResolvedValue({}),
}));

function finding(over: Partial<FindingOut> = {}): FindingOut {
  return {
    finding_id: 'f1',
    finding_type: 'payer_side',
    category: 'cost_sharing_miscalculation',
    subagent_source: 'math_person',
    voice_tier: 'A',
    facts: { gap: 640 },
    legal_claim: null,
    recommendation: null,
    citations: [],
    source_line: 'source: your plan documents · published rates',
    has_source: true,
    ...over,
  };
}

const props = { caseFileId: 'c1', existingRating: null };

/**
 * E4/H3 — the VISIBLE half of the grounding doctrine.
 *
 * The server guarantees `source_line` is always populated (either the resolved source or the
 * explicit no-source state). These tests hold the other end: the card must SHOW it. Before
 * this, the API carried the line and the card silently dropped it, so a grounded claim and an
 * ungrounded one looked identical on screen — which is the exact failure the doctrine forbids.
 */
describe('FindingCard grounding line', () => {
  it('renders the source line when the finding is grounded', () => {
    const { getByText } = render(<FindingCard finding={finding()} {...props} />);
    expect(getByText('source: your plan documents · published rates')).toBeTruthy();
  });

  it('renders the honest no-source state instead of nothing', () => {
    const unsourced = finding({
      has_source: false,
      source_line: "I can't point to a source for this one yet — I've flagged it rather than state it as fact.",
    });
    const { getByText } = render(<FindingCard finding={unsourced} {...props} />);
    expect(getByText(/can't point to a source/)).toBeTruthy();
  });

  it('never renders a finding without one of the two states', () => {
    // The invariant, asserted over both branches: whatever the server sent, it is on screen.
    for (const f of [finding(), finding({ has_source: false, source_line: 'no source yet' })]) {
      const { getByText } = render(<FindingCard finding={f} {...props} />);
      expect(getByText(f.source_line)).toBeTruthy();
    }
  });
});

/**
 * B5 (Brock 2026-08-18) — the [A]/[B] split decides the CHIP. `tier` is server-derived.
 * fact → the source renders as plain text, no chip (chips on arithmetic teach users to
 * ignore chips). rule_based + cited → the citation chip. rule_based uncited → the server
 * already swapped the line to the no-source state; the card renders that, never a chip.
 */
describe('FindingCard B5 tier rendering', () => {
  it('fact findings render their source WITHOUT a chip', () => {
    const { queryByTestId, getByText } = render(
      <FindingCard finding={finding({ tier: 'fact' })} {...props} />,
    );
    expect(queryByTestId('citation-chip')).toBeNull();
    expect(queryByTestId('fact-source-line')).toBeTruthy();
    expect(getByText('source: your plan documents · published rates')).toBeTruthy();
  });

  it('rule-based findings with a source render the citation chip', () => {
    const { getByTestId } = render(
      <FindingCard
        finding={finding({ tier: 'rule_based', source_line: 'source: No Surprises Act §2799A-1' })}
        {...props}
      />,
    );
    expect(getByTestId('citation-chip')).toBeTruthy();
  });

  it('an uncited rule-based finding renders the degraded no-source line, never a chip', () => {
    const { queryByTestId, getByTestId } = render(
      <FindingCard
        finding={finding({ tier: 'rule_based', has_source: false, source_line: 'no source yet' })}
        {...props}
      />,
    );
    expect(queryByTestId('citation-chip')).toBeNull();
    expect(getByTestId('no-source-line')).toBeTruthy();
  });
});
