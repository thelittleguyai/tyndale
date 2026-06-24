import { useWindowDimensions } from 'react-native';

/**
 * Responsive breakpoint primitive for apps/mobile (CO-14, CO-11 convention).
 *
 * Wraps useWindowDimensions so layout branches re-evaluate on rotation / window
 * resize (web). Breakpoints: phone < 640, tablet 640–1023, desktop ≥ 1024 — the
 * same 640/1024 cuts the web-marketing surface uses.
 */
export function useBreakpoint() {
  const { width } = useWindowDimensions();
  return {
    width,
    isPhone: width < 640,
    isTablet: width >= 640 && width < 1024,
    isDesktop: width >= 1024,
  };
}
