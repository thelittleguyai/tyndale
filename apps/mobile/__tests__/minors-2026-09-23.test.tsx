/** The 2026-09-23 e2e minors on the app side. */
import { render, waitFor } from '@testing-library/react-native';

import { splitTranslation } from '../lib/line-item-copy';

jest.mock('expo-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => children,
  Stack: { Screen: () => null },
}));
const mockGetSurfaceCopy = jest.fn();
jest.mock('../lib/api-client', () => ({
  getSurfaceCopy: (...a: unknown[]) => mockGetSurfaceCopy(...a),
}));

describe('verification card copy cap', () => {
  it('keeps ONE plain sentence in the heading and moves the rest under the disclosure', () => {
    const long =
      'A diagnostic arthroscopic procedure of the knee joint, performed with removal of the torn meniscal cartilage. It is usually done as an outpatient surgery. Recovery takes a few weeks.';
    const { headline, rest } = splitTranslation(long);
    expect(headline).toBe('A diagnostic arthroscopic procedure of the knee joint, performed with removal of the torn meniscal cartilage.'.slice(0, headline.length));
    expect(headline.length).toBeLessThanOrEqual(110);
    expect(rest).toMatch(/outpatient surgery/);
    expect(splitTranslation('An office visit.')).toEqual({ headline: 'An office visit.', rest: null });
    expect(splitTranslation(null)).toEqual({ headline: '', rest: null });
  });
});

describe('the branded not-found screen', () => {
  it('renders registry copy, and the plain fallback when the copy cannot be fetched', async () => {
    mockGetSurfaceCopy.mockResolvedValueOnce({ not_found_title: 'That page isn’t here.', not_found_body: 'Old link.', not_found_cta: 'Go home' });
    const NotFound = require('../app/+not-found').default;
    const { getByText, getByTestId } = render(<NotFound />);
    await waitFor(() => expect(getByText('That page isn’t here.')).toBeTruthy());
    expect(getByTestId('not-found-home')).toBeTruthy();
    mockGetSurfaceCopy.mockRejectedValueOnce(new Error('offline'));
    const again = render(<NotFound />);
    expect(again.getByText("That page isn't here.")).toBeTruthy(); // never Expo's "Unmatched Route"
    expect(again.queryByText(/Unmatched Route/)).toBeNull();
  });
});

describe('the verification nudge', () => {
  it('disappears once every card in the group is answered', () => {
    const { ThreadVerification } = require('../components/thread/ThreadVerification');
    const item = (id: string) => ({ line_item_id: id, code: '99213', code_system: 'CPT', raw_description: 'x', plain_language_translation: 'An office visit.', billed_amount: 100 });
    const payload = { intro: 'Confirm these', nudge: 'Tap one of the buttons on a card above to answer', group_index: 0, line_items: [item('a'), item('b')] };
    const half = { a: { response: 'yes', user_note: '' }, b: { response: null, user_note: '' } };
    const r1 = render(<ThreadVerification payload={payload} drafts={half} onRespond={jest.fn()} onNote={jest.fn()} />);
    expect(r1.getByTestId('verification-nudge')).toBeTruthy();
    const all = { a: { response: 'yes', user_note: '' }, b: { response: 'no', user_note: '' } };
    const r2 = render(<ThreadVerification payload={payload} drafts={all} onRespond={jest.fn()} onNote={jest.fn()} />);
    expect(r2.queryByTestId('verification-nudge')).toBeNull();
  });
});
