import { fireEvent, render } from '@testing-library/react-native';

import {
  Button,
  Card,
  Disclosure,
  ListRow,
  MetricCard,
  MomentCard,
  SectionHeader,
  StatusChip,
} from '../components/ui';
import { PressableScale } from '../components/ui/PressableScale';
import { Text } from 'react-native';

describe('PressableScale accessibility (audit 2026-08-27 carry-over)', () => {
  it('is a button to a screen reader unless the call site says otherwise', () => {
    const { getByRole, getByTestId, queryAllByRole } = render(
      <>
        <PressableScale accessibilityLabel="Upload a bill" onPress={() => {}}>
          <Text>Upload</Text>
        </PressableScale>
        <PressableScale testID="as-link" accessibilityRole="link" accessibilityLabel="Privacy policy">
          <Text>Privacy</Text>
        </PressableScale>
        <PressableScale testID="as-tab" role="tab" accessibilityLabel="Results">
          <Text>Results</Text>
        </PressableScale>
      </>,
    );
    expect(getByRole('button', { name: 'Upload a bill' })).toBeTruthy();
    expect(queryAllByRole('button')).toHaveLength(1); // the default never overrides a stated role
    expect(getByTestId('as-link').props.accessibilityRole).toBe('link');
    expect(getByTestId('as-tab').props.accessibilityRole).toBeUndefined();
    expect(getByTestId('as-tab').props.role).toBe('tab');
  });
});

describe('component kit (redesign §2)', () => {
  it('renders the primitives with content', () => {
    const { getByText } = render(
      <>
        <Card>
          <Text>card body</Text>
        </Card>
        <MetricCard label="Recovered so far" value="$400" qualifier="confirmed" progress={0.5} valueTone="success" />
        <StatusChip label="Results ready" tone="success" />
        <MomentCard>
          <Text>moment</Text>
        </MomentCard>
        <SectionHeader>Your record</SectionHeader>
        <ListRow title="Mercy Hospital" subtitle="Mar 3, 2026" meta="appeal due Dec 31" />
      </>,
    );
    expect(getByText('card body')).toBeTruthy();
    expect(getByText('Recovered so far')).toBeTruthy();
    expect(getByText('$400')).toBeTruthy();
    expect(getByText('Results ready')).toBeTruthy();
    expect(getByText('Your record')).toBeTruthy();
    expect(getByText('Mercy Hospital')).toBeTruthy();
  });

  it('Button fires onPress; Disclosure is collapsed by default and expands', () => {
    const onPress = jest.fn();
    const { getByText, queryByText } = render(
      <>
        <Button label="Add a document" onPress={onPress} variant="primary" />
        <Disclosure summary="Show what this usually looks like">
          <Text>the explainer</Text>
        </Disclosure>
      </>,
    );
    fireEvent.press(getByText('Add a document'));
    expect(onPress).toHaveBeenCalled();
    expect(queryByText('the explainer')).toBeNull(); // collapsed by default
    fireEvent.press(getByText('Show what this usually looks like'));
    expect(getByText('the explainer')).toBeTruthy();
  });
});
