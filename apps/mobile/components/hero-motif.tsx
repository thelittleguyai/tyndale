/**
 * Concentric-circle motif rendered behind the hero card subtitle.
 *
 * Visual reference: docs/design/signed_in_dashboard.png — the faint thin
 * white circles in the top-right of the welcome card, with a small dot
 * marker on the outer ring. Mirrors the logo's circular badge silhouette
 * (packages/shared/src/design-tokens.ts → logoSvg).
 */

import Svg, { Circle } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

export function HeroMotif({ size = 140, color = 'rgba(255,255,255,0.18)' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100">
      <Circle cx="50" cy="50" r="42" stroke={color} strokeWidth="0.8" fill="none" />
      <Circle cx="50" cy="50" r="30" stroke={color} strokeWidth="0.8" fill="none" />
      <Circle cx="50" cy="50" r="18" stroke={color} strokeWidth="0.8" fill="none" />
      {/* outer-ring dot marker */}
      <Circle cx="92" cy="50" r="1.5" fill={color} />
    </Svg>
  );
}
