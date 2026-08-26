/**
 * Case-card pills (mockup item 4): ONE status pill strictly from real case state, a deadline
 * pill only when a dated deadline exists, resolved shows its recovered amount.
 */
import { render } from '@testing-library/react-native';

import { RecordSection } from '../components/record/RecordSection';

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn() }) }));

const row = (over: object) => ({
  case_file_id: 'c-' + Math.random(),
  service_date: '2026-08-02',
  provider: 'UMC El Paso',
  status: 'audit_running',
  state: 'auditing',
  label: 'Audit running',
  resume: 'thread',
  three_number: null,
  open_item_count: 0,
  next_deadline: null,
  recovered_so_far: 0,
  ...over,
});

const record = (subCases: object[]) => ({
  window_months: 12,
  sub_cases: subCases,
  aggregates: {
    total_billed_reviewed: 0, total_recovered: 0, total_identified: 0,
    open_items: 0, next_check_in_date: null,
  },
  has_older: false,
});

it('one pill per case, mapped from real state', () => {
  const { getByTestId, getAllByTestId, queryByTestId } = render(
    <RecordSection
      record={record([
        row({}),
        row({ status: 'audit_incomplete', state: 'needs_documents' }),
      ]) as never}
    />,
  );
  expect(getByTestId('pill-auditing')).toBeTruthy();
  expect(getByTestId('pill-needs_documents')).toBeTruthy();
  expect(queryByTestId('pill-deadline')).toBeNull(); // no dated deadline → no pill
  expect(getAllByTestId(/^pill-/).length).toBe(2);
});

it('deadline pill only when a real dated deadline exists', () => {
  const { getByTestId } = render(
    <RecordSection
      record={record([
        row({
          status: 'audit_incomplete', state: 'needs_documents',
          next_deadline: { label: 'Appeal window', due_date: '2026-09-15', source: 'x' },
        }),
      ]) as never}
    />,
  );
  expect(getByTestId('pill-deadline')).toBeTruthy();
});

it('resolved shows its pill and the recovered amount', () => {
  const { getByTestId, getByText } = render(
    <RecordSection
      record={record([
        row({ status: 'resolved', state: 'results', recovered_so_far: 420 }),
      ]) as never}
    />,
  );
  expect(getByTestId('pill-resolved')).toBeTruthy();
  expect(getByText(/\$420/)).toBeTruthy();
});
