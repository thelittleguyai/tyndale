/**
 * Button — three visual weights (redesign §2): primary (accent fill + on-accent text), secondary
 * (hairline outline), tertiary (text-only). Use the weight to signal emphasis; don't invent new
 * button styles per screen. 44px minimum touch target.
 */
import type { ReactNode } from 'react';
import { Pressable, Text } from 'react-native';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary';

const CONTAINER: Record<ButtonVariant, string> = {
  primary: 'bg-accent active:opacity-90',
  secondary: 'border border-hairline bg-transparent active:bg-inset',
  tertiary: 'bg-transparent active:opacity-70',
};

const LABEL: Record<ButtonVariant, string> = {
  primary: 'text-on-accent',
  secondary: 'text-primary',
  tertiary: 'text-accent',
};

export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  leading,
  fullWidth = true,
  className = '',
}: {
  label: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  leading?: ReactNode;
  fullWidth?: boolean;
  className?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      className={`min-h-[44px] flex-row items-center justify-center gap-2 rounded-control px-4 py-3 ${
        CONTAINER[variant]
      } ${fullWidth ? 'w-full' : 'self-start'} ${disabled ? 'opacity-40' : ''} ${className}`}
    >
      {leading}
      <Text className={`text-body font-medium ${LABEL[variant]}`}>{label}</Text>
    </Pressable>
  );
}
