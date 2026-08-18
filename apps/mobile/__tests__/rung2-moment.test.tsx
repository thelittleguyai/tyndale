/**
 * Rung-2 surfaces (2026-08-18): the three-number moment with an X3 range + qualifier, honest
 * "not on file" anchors, and the unlock-more framing of the have/need checklist on a
 * COMPLETED audit. The honesty properties, not the styling.
 */
import { render } from '@testing-library/react-native';

import type { ThreeNumberMomentPayload, UnlockMorePayload } from '@tyndale/shared';

import { ThreeNumberMoment } from '../components/thread/MomentCards';
import { ThreadNeedsDocuments } from '../components/thread/ThreadNeedsDocuments';

const base: ThreeNumberMomentPayload = {
  variant: 'three_number',
  provider_billed: 3700,
  eob_member_responsibility: 360,
  tyndale_computed: 900,
  delta: -540,
  headline: 'Here are your three numbers.',
};

describe('ThreeNumberMoment (rung-2)', () => {
  it('renders the range AS the figure with the X3 qualifier in the same card', () => {
    const { getByTestId, getByText, queryByText } = render(
      <ThreeNumberMoment
        payload={{
          ...base,
          tyndale_computed_low: 90,
          tyndale_computed_high: 900,
          qualifier: {
            text: 'between $90.00 and $900.00 until I see your deductible',
            names: ['deductible'],
            form: 'range',
            same_unit: true,
          },
        }}
      />,
    );
    expect(getByText('$90.00–$900.00')).toBeTruthy();
    expect(getByTestId('x3-qualifier')).toBeTruthy();
    // The point value must NOT render as if precise when the honest figure is a range.
    expect(queryByText('$900.00')).toBeNull();
  });

  it('renders a point figure with no qualifier when inputs were complete (X3 tier 0)', () => {
    const { getByText, queryByTestId } = render(<ThreeNumberMoment payload={base} />);
    expect(getByText('$900.00')).toBeTruthy();
    expect(queryByTestId('x3-qualifier')).toBeNull();
  });

  it('shows "Not on file yet" for an anchor no document stated — never an invented number', () => {
    const { getByText } = render(
      <ThreeNumberMoment payload={{ ...base, eob_member_responsibility: null, delta: null }} />,
    );
    expect(getByText('Not on file yet')).toBeTruthy();
  });
});

describe('unlock-more framing', () => {
  const payload: UnlockMorePayload = {
    intro: 'Your audit is done — one more document would sharpen it.',
    item_hint: 'Checked items are on file.',
    items: [
      { key: 'eob', label: 'Explanation of Benefits (EOB)', how_to_get: 'Portal.', have: true },
      { key: 'sbc', label: 'Summary of Benefits and Coverage (SBC)', how_to_get: 'Ask HR.', have: false },
    ],
  };

  it('renders the same have/need items under the unlock card identity', () => {
    const { getByTestId, getByText } = render(
      <ThreadNeedsDocuments payload={payload} caseFileId="c1" unlock />,
    );
    expect(getByTestId('unlock-more-card')).toBeTruthy();
    expect(getByText(payload.intro)).toBeTruthy();
    expect(getByText(payload.item_hint)).toBeTruthy();
    expect(getByText('Summary of Benefits and Coverage (SBC)')).toBeTruthy();
  });

  it('the true-gate needs-documents card is unchanged (no unlock identity, no hint)', () => {
    const { getByTestId, queryByText } = render(
      <ThreadNeedsDocuments
        payload={{ intro: 'To finish your audit…', items: payload.items }}
        caseFileId="c1"
      />,
    );
    expect(getByTestId('needs-documents-card')).toBeTruthy();
    expect(queryByText(payload.item_hint)).toBeNull();
  });
});
