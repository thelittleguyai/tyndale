/**
 * The status card's header is the SERVER's decision (e2e re-test 2026-09-23 item 2). The client
 * used to say "Audit ready" whenever every bar was done — and a system_error run marks every
 * bar done, so the card said "Audit ready ✓" above the apology.
 */
import { render } from '@testing-library/react-native';

import type { StatusCardPayload } from '@tyndale/shared';

import { StatusCard } from '../components/thread/StatusCard';

const stages = (last: 'done' | 'failed' | 'waiting'): StatusCardPayload['stages'] => [
  { key: 'extraction', label: 'Reading your bill', state: 'done' },
  { key: 'translate', label: 'Sorting the charges', state: 'done' },
  { key: 'encounter', label: 'Confirming what happened', state: 'done' },
  { key: 'audit', label: 'Checking every charge', state: last },
];

describe('StatusCard variants', () => {
  it('a failed audit says what the server says — never "Audit ready"', () => {
    const { getByText, queryByText, getByTestId } = render(
      <StatusCard
        payload={{
          stages: stages('failed'),
          terminal: true,
          variant: 'failed',
          headline: 'Paused — a problem on my end',
        }}
      />,
    );
    expect(getByTestId('status-card-failed')).toBeTruthy();
    expect(getByText('Paused — a problem on my end')).toBeTruthy();
    expect(queryByText('Audit ready')).toBeNull();
  });

  it('a needs-documents audit shows the waiting stage and its own header', () => {
    const { getByText, getAllByText, queryByText } = render(
      <StatusCard
        payload={{
          stages: stages('waiting'),
          terminal: true,
          variant: 'needs_documents',
          headline: 'Paused — waiting on your documents',
        }}
      />,
    );
    expect(getByText('Paused — waiting on your documents')).toBeTruthy();
    expect(getAllByText('…')).toHaveLength(2); // the header's marker and the waiting stage's
    expect(queryByText('Audit ready')).toBeNull();
  });

  it('a complete audit is ready', () => {
    const { getByText } = render(
      <StatusCard
        payload={{ stages: stages('done'), terminal: true, variant: 'ready', headline: 'Audit ready' }}
      />,
    );
    expect(getByText('Audit ready')).toBeTruthy();
  });

  it('a variant with no header renders none', () => {
    const { queryByText, getByTestId } = render(
      <StatusCard
        payload={{
          stages: stages('done'),
          terminal: false,
          paused: true,
          variant: 'paused',
          headline: null,
        }}
      />,
    );
    expect(getByTestId('status-card-paused')).toBeTruthy();
    expect(queryByText('Audit ready')).toBeNull();
    expect(queryByText('Working on your audit')).toBeNull();
  });

  it('a card from before the fix still renders (the server re-projects it on read)', () => {
    const { getByText } = render(
      <StatusCard payload={{ stages: stages('done'), terminal: true }} />,
    );
    expect(getByText('Audit ready')).toBeTruthy();
  });
});
