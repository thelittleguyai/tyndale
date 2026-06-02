import { fireEvent, render } from '@testing-library/react-native';

import { CitationChip } from '../../components/chat/CitationChip';
import { ToolCallIndicator } from '../../components/chat/ToolCallIndicator';

describe('CitationChip', () => {
  it('truncates a long title and fires onPress with the citation', () => {
    const onPress = jest.fn();
    const citation = {
      title: 'A very long citation source title that exceeds the limit',
      source_id: 's',
    };
    const { getByText } = render(<CitationChip citation={citation} onPress={onPress} />);
    const label = getByText(/A very long citation source/);
    expect(String(label.props.children).endsWith('…')).toBe(true);
    fireEvent.press(label);
    expect(onPress).toHaveBeenCalledWith(citation);
  });
});

describe('ToolCallIndicator', () => {
  it('shows the active subagent + humanized action', () => {
    const { getByText } = render(
      <ToolCallIndicator tools={[{ tool_name: 'pg_case_file_get', subagent: 'Bill Detective' }]} />,
    );
    expect(getByText(/Bill Detective is reading your case file/)).toBeTruthy();
  });

  it('renders nothing when there are no active tools', () => {
    const { toJSON } = render(<ToolCallIndicator tools={[]} />);
    expect(toJSON()).toBeNull();
  });
});
