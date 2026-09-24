/** e2e round 3 R6 — the branch card's **bold**, and a stage that could not run. */
import { render } from '@testing-library/react-native';

import { BranchCard } from '../components/thread/BranchCard';
import { StatusCard } from '../components/thread/StatusCard';

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe('the wrong-document card', () => {
  it("renders Brock's bold as bold — never the asterisks", () => {
    const text =
      "That looks like an insurance card, not a bill or EOB — so there's nothing for me to audit on it yet. To check a bill, I need your **itemized medical bill** or your **Explanation of Benefits (EOB)**.";
    const r = render(<BranchCard kind="wrongdoc" text={text} caseFileId="cf" />);
    expect(JSON.stringify(r.toJSON())).not.toContain('**');
    expect(r.getByText('itemized medical bill')).toBeTruthy();
    expect(r.getByTestId('branch-action-wrongdoc')).toBeTruthy();
  });
});

describe('the paused status card', () => {
  it('marks a stage that could not run with a dash, never a tick', () => {
    const r = render(
      <StatusCard
        payload={{
          stages: [
            { key: 'extraction', label: 'Reading your bill', state: 'done' },
            { key: 'translate', label: 'Checking each charge', state: 'done' },
            { key: 'encounter', label: "Comparing your insurer's math", state: 'skipped' },
            { key: 'audit', label: 'Finding what you owe', state: 'waiting' },
          ],
          terminal: true,
          variant: 'needs_documents',
          headline: 'Paused — waiting on your documents',
        }}
      />,
    );
    expect(r.getByTestId('stage-skipped-encounter').props.children).toBe('—');
    expect(r.getAllByText('✓')).toHaveLength(2); // only the two stages that ran
  });
});
