import { fireEvent, render } from '@testing-library/react-native';

import { ThemeToggle } from '../components/ui/ThemeToggle';
import { loadThemeMode } from '../theme/mode-store';

describe('ThemeToggle (Settings appearance switch)', () => {
  it('renders Light/Dark/System and persists the selected mode', () => {
    const { getByText } = render(<ThemeToggle />);
    expect(getByText('Light')).toBeTruthy();
    expect(getByText('Dark')).toBeTruthy();
    expect(getByText('System')).toBeTruthy();

    fireEvent.press(getByText('Dark'));
    expect(loadThemeMode()).toBe('dark');

    fireEvent.press(getByText('System'));
    expect(loadThemeMode()).toBe('system');
  });
});
