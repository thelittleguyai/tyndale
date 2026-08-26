/**
 * Coverage-number checklist rows (Brock image-3 item 2): tap-to-open inline input, SAVE as
 * the only state change (D4b), "not sure" opt-out, visit-confirm candidate chips, completed
 * strikethrough state.
 */
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import { ThreadNeedsDocuments } from '../components/thread/ThreadNeedsDocuments';

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn() }) }));
const mockSave = jest.fn().mockResolvedValue(undefined);
jest.mock('../lib/api-client', () => ({ saveCoverageInput: (...a: unknown[]) => mockSave(...a) }));

const payload = {
  intro: 'To finish your audit:',
  items: [
    { key: 'eob', label: 'Explanation of Benefits (EOB)', how_to_get: 'ask your insurer', have: false },
  ],
  coverage_items: [
    { key: 'deductible_met', kind: 'number' as const, label: 'Amount spent toward deductible before this visit', value: null, not_sure: false },
    { key: 'oop_max_amount', kind: 'number' as const, label: 'Out-of-pocket max amount', value: 6000, not_sure: false },
    {
      key: 'visit_confirm', kind: 'visit_confirm' as const, label: 'Confirm what your visit was for',
      value: null, not_sure: false, candidates: ['MRI of the brain'],
    },
  ],
};

beforeEach(() => mockSave.mockClear());

it('renders number rows; completed one shows its value struck through', () => {
  const { getByTestId, getByText } = render(
    <ThreadNeedsDocuments payload={payload} caseFileId="c1" />,
  );
  expect(getByText('Amount spent toward deductible before this visit')).toBeTruthy();
  expect(getByTestId('coverage-value-oop_max_amount').props.children).toBe('$6,000');
});

it('saves a typed number via the inline input — tap is the only state change', async () => {
  const { getByTestId } = render(<ThreadNeedsDocuments payload={payload} caseFileId="c1" />);
  fireEvent.press(getByTestId('coverage-item-deductible_met'));
  fireEvent.changeText(getByTestId('coverage-input-deductible_met'), '$1,500');
  expect(mockSave).not.toHaveBeenCalled(); // typing alone never writes
  fireEvent.press(getByTestId('coverage-save-deductible_met'));
  await waitFor(() => expect(mockSave).toHaveBeenCalledWith('c1', 'deductible_met', 1500, false));
});

it('"not sure" posts the honest opt-out', async () => {
  const { getByTestId } = render(<ThreadNeedsDocuments payload={payload} caseFileId="c1" />);
  fireEvent.press(getByTestId('coverage-item-deductible_met'));
  fireEvent.press(getByTestId('coverage-notsure-deductible_met'));
  await waitFor(() =>
    expect(mockSave).toHaveBeenCalledWith('c1', 'deductible_met', undefined, true),
  );
});

it('visit-confirm chips save the tapped candidate', async () => {
  const { getByTestId } = render(<ThreadNeedsDocuments payload={payload} caseFileId="c1" />);
  fireEvent.press(getByTestId('coverage-item-visit_confirm'));
  fireEvent.press(getByTestId('visit-candidate-MRI of the brain'));
  await waitFor(() =>
    expect(mockSave).toHaveBeenCalledWith('c1', 'visit_confirm', 'MRI of the brain', false),
  );
});
