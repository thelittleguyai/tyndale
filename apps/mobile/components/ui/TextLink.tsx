/**
 * TextLink — a text-weight action that sits BESIDE content ("Change", "See an example"): the
 * label is inside the Pressable, the hit area is a 44 px minimum on both axes (min-h/min-w on
 * web, plus hitSlop on native), and it never stretches — `shrink-0` + `self-start`, so a
 * neighbouring flex-1 column keeps the row. The tertiary Button is full-width by default; beside
 * a flex-1 label it took the whole row and squeezed every label to one character per line
 * (e2e round 3 R2).
 */
import { Pressable, Text } from 'react-native';

export function TextLink({
  label,
  onPress,
  disabled = false,
  className = '',
  testID,
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  className?: string;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      hitSlop={8}
      testID={testID}
      className={`min-h-[44px] min-w-[44px] shrink-0 items-center justify-center self-start rounded-control px-2 active:opacity-70 ${
        disabled ? 'opacity-40' : ''
      } ${className}`}
    >
      <Text className="text-body font-medium text-accent">{label}</Text>
    </Pressable>
  );
}
