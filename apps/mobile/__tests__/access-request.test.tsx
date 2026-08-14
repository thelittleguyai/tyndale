/**
 * Statutory-rights intake reachability (deep review finding 4).
 *
 * The server route and its encrypted event have existed for weeks; the gap was that no screen
 * called them. So the assertions that matter here are (a) the screen submits, and (b) the
 * confirmation says nothing about whether the named person is in our data — the receipt is
 * identical either way, and any branch on the result would be the disclosure the whole intake
 * is designed to avoid.
 */
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockSubmit = jest.fn();
const mockGetCopy = jest.fn();
jest.mock('../lib/api-client', () => ({
  submitAccessRequest: (...a: unknown[]) => mockSubmit(...a),
  getSurfaceCopy: (...a: unknown[]) => mockGetCopy(...a),
}));

import AccessRequestScreen from '../app/(app)/access-request';

const RECEIPT =
  'Your request has been recorded and someone will follow up at the contact you gave.';

beforeEach(() => {
  mockSubmit.mockReset().mockResolvedValue({ received: true, message: RECEIPT });
  mockGetCopy.mockReset().mockResolvedValue({});
});

function fill(getByTestId: (id: string) => any) {
  fireEvent.changeText(getByTestId('access-name'), 'Jordan Q. Testpatient');
  fireEvent.changeText(getByTestId('access-contact'), 'jordan@example.test');
}

describe('AccessRequestScreen', () => {
  it('submits the typed request to the existing route', async () => {
    const { getByTestId } = render(<AccessRequestScreen />);
    fill(getByTestId);
    fireEvent.press(getByTestId('access-type-deletion'));
    fireEvent.press(getByTestId('access-submit'));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalled());
    expect(mockSubmit.mock.calls[0][0]).toMatchObject({
      request_type: 'deletion',
      patient_name: 'Jordan Q. Testpatient',
      contact: 'jordan@example.test',
    });
  });

  it('renders the server receipt verbatim and discloses nothing', async () => {
    const { getByTestId, getByText, queryByText } = render(<AccessRequestScreen />);
    fill(getByTestId);
    fireEvent.press(getByTestId('access-submit'));
    await waitFor(() => expect(getByTestId('access-receipt')).toBeTruthy());
    expect(getByText(RECEIPT)).toBeTruthy();
    // No found/not-found language may appear — the presence of either IS the disclosure.
    for (const tell of [/we found/i, /no record/i, /not in our/i, /we have data/i]) {
      expect(queryByText(tell)).toBeNull();
    }
  });

  it('will not submit without a name and a contact', () => {
    const { getByTestId } = render(<AccessRequestScreen />);
    fireEvent.press(getByTestId('access-submit'));
    expect(mockSubmit).not.toHaveBeenCalled();
    fireEvent.changeText(getByTestId('access-name'), 'Someone');
    fireEvent.press(getByTestId('access-submit'));
    expect(mockSubmit).not.toHaveBeenCalled(); // still no contact to reply to
  });

  it('renders even when the copy call fails — a legal right cannot depend on a fetch', async () => {
    mockGetCopy.mockRejectedValue(new Error('offline'));
    const { getByTestId } = render(<AccessRequestScreen />);
    await waitFor(() => expect(getByTestId('access-submit')).toBeTruthy());
    expect(getByTestId('access-type-access')).toBeTruthy();
  });

  it('surfaces a send failure instead of implying the request was recorded', async () => {
    mockSubmit.mockRejectedValue(new Error('500'));
    const { getByTestId, queryByTestId, getByText } = render(<AccessRequestScreen />);
    fill(getByTestId);
    fireEvent.press(getByTestId('access-submit'));
    await waitFor(() => expect(getByText(/didn't send/i)).toBeTruthy());
    expect(queryByTestId('access-receipt')).toBeNull();
  });
});
