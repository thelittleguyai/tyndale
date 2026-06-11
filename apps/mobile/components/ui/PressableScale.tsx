/**
 * PressableScale — drop-in Pressable with built-in press feedback: scales to
 * 0.97 and dims to 0.85 opacity while pressed. Uses the Pressable
 * style-function pattern, which works identically on web and native (and on
 * web the global.css transition rule for [role="button"] makes it animate).
 *
 * NativeWind className styles still apply (cssInterop merges them into the
 * resolved style before our function runs). forwardRef so it works inside
 * expo-router's <Link asChild>.
 */

import { forwardRef } from 'react';
import {
  Pressable,
  type PressableProps,
  type StyleProp,
  type View,
  type ViewStyle,
} from 'react-native';

export type PressableScaleProps = Omit<PressableProps, 'style'> & {
  /** Static style only — the pressed transform is handled internally. */
  style?: StyleProp<ViewStyle>;
};

export const PressableScale = forwardRef<View, PressableScaleProps>(
  function PressableScale({ style, ...rest }, ref) {
    return (
      <Pressable
        ref={ref}
        {...rest}
        style={({ pressed }) => [
          style,
          pressed && { transform: [{ scale: 0.97 }], opacity: 0.85 },
        ]}
      />
    );
  },
);
